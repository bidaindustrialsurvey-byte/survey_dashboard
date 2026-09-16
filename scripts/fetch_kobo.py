"""
Pull submissions from KoboToolbox and write aggregated counts to data.json.

Only totals and counts leave this script. No firm names, registration
numbers or other firm-level details are written to data.json.

Environment variables (set as GitHub Secrets):
  KOBO_TOKEN       API token from your Kobo account settings
  KOBO_ASSET_UID   form UID, the part after /forms/ in the form URL
  KOBO_SERVER      optional, default https://kf.kobotoolbox.org
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import requests

# ------------------------------------------------------------------
# FIELD MAPPING — using the real XML names from your XLSForm
# ------------------------------------------------------------------
FIELDS = {
    # Uses factory division if present, else interview division
    "division":      "Q2_2_1_a",              # a. Division (factory)
    "division_alt":  "Q2_1_2_a",              # 2.1.2.a Interview division (fallback)
    "location":      "Q2_5_1",                # 2.5.1 Location of industry
    "reg_authority": "Q2_6_1",                # 2.6.1 Host Authority (IPA)
    "ownership":     "Q2_8_2",                # 2.8.2 Type of private enterprise
    "production":    "Q2_7_1",                # 2.7.1 Status of production
    "exporter":      "main/main7/grp7/Q7_2_exporter_type",
    "expansion":     "Q11_1",                 # 11.1 Plan to expand
}

# Optional: additional info for BIDA/ADM-style labeling
# (used only to look up choice labels)

# Bangladeshi workforce by employment type and gender
WORKFORCE = {
    "Regular":     {"male": "q3a21a_bd_male",  "female": "q3a21b_bd_female",  "third": "q3a21c_bd_thirdg"},
    "Contractual": {"male": "q3a22a_bd_male",  "female": "q3a22b_bd_female",  "third": "q3a22c_bd_thirdg"},
    "Casual":      {"male": "q3a23a_bd_male",  "female": "q3a23b_bd_female",  "third": "q3a23c_bd_thirdg"},
    "Family":      {"male": "q3a25a_bd_male",  "female": "q3a25b_bd_female",  "third": "q3a25c_bd_thirdg"},
    "Proprietor":  {"male": "q3a26a_bd_male",  "female": "q3a26b_bd_female",  "third": "q3a26c_bd_thirdg"},
}

MAX_HISTORY_DAYS = 400
TZ = timezone(timedelta(hours=6))  # Asia/Dhaka

DIVISIONS = ["Dhaka", "Chattogram", "Khulna", "Rajshahi", "Sylhet", "Barishal", "Mymensingh", "Rangpur"]

# Kobo choice codes for divisions (from choices sheet, list "fac_division")
DIVISION_CODE_TO_NAME = {
    "10": "Barishal",
    "20": "Chattogram",
    "30": "Dhaka",
    "40": "Khulna",
    "45": "Mymensingh",
    "50": "Rajshahi",
    "55": "Rangpur",
    "60": "Sylhet",
}

DEBUG = os.environ.get("KOBO_DEBUG") == "1"


# ------------------------------------------------------------------
# KOBO API
# ------------------------------------------------------------------
def kobo_get(url, token):
    r = requests.get(url, headers={"Authorization": f"Token {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_all(server, uid, token):
    asset = kobo_get(f"{server}/api/v2/assets/{uid}/?format=json", token)
    url = f"{server}/api/v2/assets/{uid}/data/?format=json&limit=1000"
    rows = []
    while url:
        page = kobo_get(url, token)
        rows.extend(page.get("results", []))
        url = page.get("next")
    return asset, rows


def choice_labels(asset):
    content = asset.get("content", {})
    lists = defaultdict(dict)
    for ch in content.get("choices", []):
        label = ch.get("label")
                if isinstance(label, list):
            picked = None
            for l in label:
                if isinstance(l, dict) and str(l.get("language","")).startswith("English"):
                    picked = l.get("value"); break
                if isinstance(l, str) and l:
                    picked = l; break
            if not picked and label:
                first = label[0]
                picked = first.get("value") if isinstance(first, dict) else first
            label = picked
        elif isinstance(label, dict):
            label = label.get("value")
        lists[ch.get("list_name")][ch.get("name")] = label or ch.get("name")
    out = {}
    for q in content.get("survey", []):
        lst = q.get("select_from_list_name")
        if lst:
            out[q.get("name") or q.get("$autoname")] = lists.get(lst, {})
    return out
    for q in content.get("survey", []):
        lst = q.get("select_from_list_name")
        if lst:
            out[q.get("name") or q.get("$autoname")] = lists.get(lst, {})
    return out


# ------------------------------------------------------------------
# AGGREGATION
# ------------------------------------------------------------------
def value(row, name):
    if name in row:
        return row[name]
    for k, v in row.items():
        if k.endswith("/" + name):
            return v
    # Fallback: fuzzy match
    target = "".join(c.lower() for c in name if c.isalnum())
    for k, v in row.items():
        if "".join(c.lower() for c in k if c.isalnum()) == target:
            return v
    return None


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _split_multi(v):
    """Kobo returns multi-select as a space-separated string of codes."""
    if v in (None, ""):
        return []
    return str(v).split()


def counts(rows, field, labels):
    c = Counter()
    hits = 0
    for r in rows:
        v = value(r, field)
        if v in (None, ""):
            continue
        hits += 1
        # Multi-select: split and count each code
        parts = _split_multi(v)
        if len(parts) > 1:
            for p in parts:
                c[labels.get(field, {}).get(p, p)] += 1
        else:
            c[labels.get(field, {}).get(v, v)] += 1
    if DEBUG:
        print(f"  [{field}] matched {hits} rows, {len(c)} unique values")
    ordered = c.most_common()
    return {"labels": [k for k, _ in ordered], "values": [n for _, n in ordered]}


def parse_time(s):
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def aggregate(rows, labels, now=None):
    now = now or datetime.now(TZ)
    today = now.date()

    # Division: prefer factory division, fall back to interview division
    div = {d: 0 for d in DIVISIONS}
    div_raw = labels.get(FIELDS["division"], {})
    div_alt_raw = labels.get(FIELDS["division_alt"], {})
    for r in rows:
        raw = value(r, FIELDS["division"]) or value(r, FIELDS["division_alt"])
        if raw in (None, ""):
            continue
        name = DIVISION_CODE_TO_NAME.get(str(raw).strip())
        if not name:
            name = div_raw.get(raw) or div_alt_raw.get(raw)
        if name in div:
            div[name] += 1

    # Daily counts
    per_day = Counter()
    for r in rows:
        t = parse_time(r.get("_submission_time"))
        if t:
            per_day[t.astimezone(TZ).date()] += 1
    first = min(per_day) if per_day else today
    first = max(first, today - timedelta(days=MAX_HISTORY_DAYS - 1))
    dates = [first + timedelta(days=i) for i in range((today - first).days + 1)]

    # Workforce (Bangladeshi)
    wf = {"categories": list(WORKFORCE), "male": [], "female": [], "third": []}
    for cat, g in WORKFORCE.items():
        for k in ("male", "female", "third"):
            wf[k].append(int(sum(num(value(r, g[k])) for r in rows)))

    return {
        "updated_at": now.isoformat(),
        "source": "kobo",
        "total": len(rows),
        "divisions": div,
        "location": counts(rows, FIELDS["location"], labels),
        "reg_authority": counts(rows, FIELDS["reg_authority"], labels),
        "ownership": counts(rows, FIELDS["ownership"], labels),
        "production": counts(rows, FIELDS["production"], labels),
        "exporter": counts(rows, FIELDS["exporter"], labels),
        "expansion": counts(rows, FIELDS["expansion"], labels),
        "workforce": wf,
        "timeline": {"dates": [d.isoformat() for d in dates], "counts": [per_day[d] for d in dates]},
    }
  def choice_labels(asset):
    content = asset.get("content", {})
    lists = defaultdict(dict)
    for ch in content.get("choices", []):
        label = ch.get("label")
        # Kobo may return label as a string, a dict, or a list of dicts/strings
        if isinstance(label, list):
            # Try to find the English entry; fall back to the first entry
            picked = None
            for l in label:
                if isinstance(l, dict) and str(l.get("language","")).startswith("English"):
                    picked = l.get("value"); break
                if isinstance(l, str) and l:
                    picked = l; break
            if not picked and label:
                first = label[0]
                picked = first.get("value") if isinstance(first, dict) else first
            label = picked
        elif isinstance(label, dict):
            label = label.get("value")
        lists[ch.get("list_name")][ch.get("name")] = label or ch.get("name")
    out = {}
    for q in content.get("survey", []):
        lst = q.get("select_from_list_name")
        if lst:
            out[q.get("name") or q.get("$autoname")] = lists.get(lst, {})
    return out
