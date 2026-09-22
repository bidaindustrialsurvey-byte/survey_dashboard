"""
Read the "unsuccessful surveys" Google Sheet and write aggregated counts to
data-unsuccessful.json for the Census dashboard.

Only counts are written (total, counts per reason, counts per division).
Firm names, addresses and phone numbers in the sheet never reach the website.

Environment variables (GitHub Secrets):
  UNSUCCESSFUL_SHEET_URL   link to the sheet. Any of these works:
     - the normal address from the browser, e.g.
       https://docs.google.com/spreadsheets/d/<ID>/edit#gid=<GID>
       (sheet shared as "Anyone with the link: Viewer")
     - a "Publish to web" CSV link (...pub?gid=...&output=csv)
Optional:
  UNSUCCESSFUL_REASON_COLUMN     header of the reason column   (default: "Status", else the first header containing "reason")
  UNSUCCESSFUL_DIVISION_COLUMN   header of the division column (default: first header containing "division")
"""
import csv
import io
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

TZ = timezone(timedelta(hours=6))   # Asia/Dhaka
OUT = os.path.join(os.path.dirname(__file__), "..", "data-unsuccessful.json")

DIVISIONS = ["Dhaka", "Chattogram", "Khulna", "Rajshahi", "Sylhet", "Barishal", "Mymensingh", "Rangpur"]
DIVISION_ALIASES = {
    "chittagong": "Chattogram", "ctg": "Chattogram", "barisal": "Barishal", "mymensing": "Mymensingh",
    "ঢাকা": "Dhaka", "চট্টগ্রাম": "Chattogram", "খুলনা": "Khulna", "রাজশাহী": "Rajshahi",
    "সিলেট": "Sylhet", "বরিশাল": "Barishal", "ময়মনসিংহ": "Mymensingh", "রংপুর": "Rangpur",
}


def csv_url(url):
    """Turn a normal Google Sheets link into its CSV export link."""
    url = url.strip()
    if "output=csv" in url or "format=csv" in url:
        return url
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        return url
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")


def find_column(headers, wanted, keyword):
    if wanted:
        for h in headers:
            if h.strip().lower() == wanted.strip().lower():
                return h
        sys.exit(f"Column '{wanted}' not found. Columns in the sheet: {headers}")
    for h in headers:
        if keyword in h.lower():
            return h
    return None


def canon_division(v):
    s = (v or "").strip()
    if not s:
        return None
    for d in DIVISIONS:
        if s.lower() == d.lower() or s.lower().startswith(d.lower()):
            return d
    return DIVISION_ALIASES.get(s.lower()) or DIVISION_ALIASES.get(s)


def clean(text):
    return " ".join((text or "").split())


def aggregate(rows, reason_col, division_col):
    rows = [r for r in rows if any(clean(v) for v in r.values())]   # skip blank lines
    reasons = Counter()
    spelling = {}
    for r in rows:
        reason = clean(r.get(reason_col, "")) if reason_col else ""
        reason = reason or "Not specified"
        key = reason.lower()
        spelling.setdefault(key, Counter())[reason] += 1
        reasons[key] += 1
    ordered = reasons.most_common()
    divs = {d: 0 for d in DIVISIONS}
    unplaced = 0
    if division_col:
        for r in rows:
            d = canon_division(r.get(division_col))
            if d:
                divs[d] += 1
            else:
                unplaced += 1
    return {
        "updated_at": datetime.now(TZ).isoformat(),
        "source": "google-sheet",
        "total": len(rows),
        "reasons": {
            "labels": [spelling[k].most_common(1)[0][0] for k, _ in ordered],
            "values": [n for _, n in ordered],
        },
        "divisions": divs if division_col else None,
        "unplaced": unplaced,
    }


def main():
    url = os.environ.get("UNSUCCESSFUL_SHEET_URL")
    if not url:
        print("[unsuccessful] UNSUCCESSFUL_SHEET_URL not set, skipping.")
        return
    r = requests.get(csv_url(url), timeout=60)
    if r.status_code != 200 or "text/html" in r.headers.get("content-type", ""):
        sys.exit("[unsuccessful] Could not read the sheet as CSV. Share it as 'Anyone with the link: Viewer', "
                 "or use File > Share > Publish to web > CSV, and check the link in the secret.")
    r.encoding = "utf-8"
    reader = csv.DictReader(io.StringIO(r.text))
    headers = [h for h in (reader.fieldnames or []) if h]
    rows = list(reader)
    reason_col = find_column(headers, os.environ.get("UNSUCCESSFUL_REASON_COLUMN") or ("Status" if any(h.strip().lower() == "status" for h in headers) else None), "reason")
    if not reason_col:
        print(f"[unsuccessful] No 'Status' or 'Reason' column. Columns in the sheet: {headers}")
        print("[unsuccessful] Rename the reason column, or set UNSUCCESSFUL_REASON_COLUMN. Skipping.")
        return
    division_col = find_column(headers, os.environ.get("UNSUCCESSFUL_DIVISION_COLUMN"), "division")
    print(f"[unsuccessful] columns in sheet: {headers}")
    print(f"[unsuccessful] reason column: {reason_col!r}, division column: {division_col!r}")
    data = aggregate(rows, reason_col, division_col)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print(f"[unsuccessful] wrote data-unsuccessful.json: {data['total']} firms")
    print(f"  reasons: {dict(zip(data['reasons']['labels'], data['reasons']['values']))}")
    if data["divisions"]:
        print(f"  divisions: {data['divisions']} (no division: {data['unplaced']})")


if __name__ == "__main__":
    main()
