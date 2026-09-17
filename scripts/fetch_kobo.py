"""
Pull submissions from KoboToolbox and write aggregated counts for the dashboard.

Usage:
  python scripts/fetch_kobo.py census   -> data.json         (KOBO_TOKEN, KOBO_ASSET_UID)
  python scripts/fetch_kobo.py survey   -> data-survey.json  (KOBO_TOKEN, KOBO_ASSET_UID_SURVEY)

Both projects live in the same Kobo account, so they share one token.

Chart labels are written in both English and Bangla, taken from the form itself.
Only totals and counts are written. No firm names, contacts or registration
numbers leave this script.

Each field is found in this order:
  1. the question name set below (e.g. "Q2_5_1")
  2. if that name is not in the data, the question whose ENGLISH label starts
     with the given text (e.g. "2.5.1.")
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import requests

MAX_HISTORY_DAYS = 400
TZ = timezone(timedelta(hours=6))   # Asia/Dhaka
DEBUG = os.environ.get("KOBO_DEBUG") == "1"

DATASETS = {
    "census": {"env": "", "out": "data.json"},
    "survey": {"env": "_SURVEY", "out": "data-survey.json"},
}

# (question name, English label starts with). Used for both forms; if the domestic
# survey uses different names, the label fallback finds them, or add a SURVEY_FIELDS block.
FIELDS = {
    "location":      ("Q2_5_1", "2.5.1."),
    "reg_authority": ("Q2_6_1", "2.6.1."),
    "ownership":     ("Q2_8_2", "2.8.2."),
    "production":    ("Q2_7_1", "2.7.1."),
}

# Division of the firm: first answer found wins.
# Factory, headquarters and registered address all use the label "a. Division",
# so they are picked by their order in the form (1st, 2nd, 3rd).
DIVISION_SOURCES = [
    ("Q2_2_1_a", ("a. Division", 1)),   # factory address
    (None,       ("a. Division", 2)),   # headquarter address
    ("Q2_1_2_a", ("2.1.2.a.", 1)),      # division where interview was held
    (None,       ("a. Division", 3)),   # registered address
]

DIVISIONS = ["Dhaka", "Chattogram", "Khulna", "Rajshahi", "Sylhet", "Barishal", "Mymensingh", "Rangpur"]
DIVISION_ALIASES = {
    "10": "Barishal", "20": "Chattogram", "30": "Dhaka", "40": "Khulna",
    "45": "Mymensingh", "50": "Rajshahi", "55": "Rangpur", "60": "Sylhet",
    "chittagong": "Chattogram", "barisal": "Barishal",
    "ঢাকা": "Dhaka", "চট্টগ্রাম": "Chattogram", "খুলনা": "Khulna", "রাজশাহী": "Rajshahi",
    "সিলেট": "Sylhet", "বরিশাল": "Barishal", "ময়মনসিংহ": "Mymensingh", "রংপুর": "Rangpur",
}


# ------------------------------------------------------------------ Kobo API
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


# ------------------------------------------------------------------ Form definition
class Form:
    def __init__(self, asset):
        content = asset.get("content", {}) or {}
        trans = [str(t or "").lower() for t in (content.get("translations") or [])]
        self.idx = {"en": 0, "bn": 0}
        for i, t in enumerate(trans):
            if "english" in t or "(en)" in t:
                self.idx["en"] = i
            if "bengali" in t or "bangla" in t or "(bn)" in t or "বাংলা" in t:
                self.idx["bn"] = i
        if trans and not any("bengali" in t or "bangla" in t or "(bn)" in t or "বাংলা" in t for t in trans):
            self.idx["bn"] = self.idx["en"]
        self.translations = content.get("translations")

        lists = defaultdict(dict)
        for ch in content.get("choices", []):
            lists[ch.get("list_name")][str(ch.get("name"))] = {
                "en": self.label(ch.get("label"), "en", ch.get("name")),
                "bn": self.label(ch.get("label"), "bn", ch.get("name")),
            }
        self.questions = []   # (name, English label, type)
        self.choices = {}
        for q in content.get("survey", []):
            name = q.get("name") or q.get("$autoname")
            if not name:
                continue
            en = " ".join(str(self.label(q.get("label"), "en", "")).split())
            self.questions.append((name, en, str(q.get("type", ""))))
            if q.get("select_from_list_name"):
                self.choices[name] = lists.get(q["select_from_list_name"], {})
        self.types = {n: t for n, _, t in self.questions}

    def label(self, label, lang, fallback):
        i = self.idx[lang]
        if isinstance(label, list):
            if i < len(label) and label[i]:
                return label[i]
            return next((x for x in label if x), fallback)
        if isinstance(label, dict):
            return label.get("value") or fallback
        return label or fallback

    def by_label(self, start, nth=1):
        hits = [n for n, lab, _ in self.questions if lab.lower().startswith(start.lower())]
        return hits[nth - 1] if len(hits) >= nth else None

    def choice(self, name, code):
        c = self.choices.get(name, {}).get(str(code))
        return c or {"en": str(code), "bn": str(code)}

    def is_multi(self, name):
        return self.types.get(name, "").startswith("select_multiple")


# ------------------------------------------------------------------ Helpers
def value(row, name):
    if not name:
        return None
    if name in row:
        return row[name]
    for k, v in row.items():
        if k.endswith("/" + name):
            return v
    return None


def present(rows, name):
    return bool(name) and any(value(r, name) not in (None, "") for r in rows)


def resolve(rows, form, name, label, nth=1):
    if present(rows, name):
        return name
    return (form.by_label(label, nth) if label else None) or name


def canon_division(v):
    if v in (None, ""):
        return None
    s = str(v).strip()
    for d in DIVISIONS:
        if s.lower() == d.lower():
            return d
    return DIVISION_ALIASES.get(s.lower()) or DIVISION_ALIASES.get(s)


def counts(rows, form, name):
    c = Counter()
    for r in rows:
        v = value(r, name)
        if v in (None, ""):
            continue
        for code in (str(v).split() if form.is_multi(name) else [v]):
            c[str(code)] += 1
    ordered = c.most_common()
    return {
        "labels": {
            "en": [form.choice(name, k)["en"] for k, _ in ordered],
            "bn": [form.choice(name, k)["bn"] for k, _ in ordered],
        },
        "values": [n for _, n in ordered],
    }


def parse_time(s):
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ------------------------------------------------------------------ Aggregation
def aggregate(rows, form, now=None):
    now = now or datetime.now(TZ)
    today = now.date()

    f = {k: resolve(rows, form, n, lab) for k, (n, lab) in FIELDS.items()}
    div_names = [resolve(rows, form, n, lab, nth) for n, (lab, nth) in DIVISION_SOURCES]

    div = {d: 0 for d in DIVISIONS}
    unplaced = 0
    for r in rows:
        name = None
        for q in div_names:
            raw = value(r, q)
            if raw in (None, ""):
                continue
            ch = form.choice(q, raw)
            name = canon_division(raw) or canon_division(ch["en"]) or canon_division(ch["bn"])
            if name:
                break
        if name:
            div[name] += 1
        else:
            unplaced += 1

    per_day = Counter()
    for r in rows:
        t = parse_time(r.get("_submission_time"))
        if t:
            per_day[t.astimezone(TZ).date()] += 1
    first = min(per_day) if per_day else today
    first = max(first, today - timedelta(days=MAX_HISTORY_DAYS - 1))
    dates = [first + timedelta(days=i) for i in range((today - first).days + 1)]

    if DEBUG:
        print(f"Form languages: {form.translations} -> en index {form.idx['en']}, bn index {form.idx['bn']}")
        print("Fields used:")
        for k, v in f.items():
            print(f"  {k}: {v}")
        print(f"  division (in order): {div_names}")
        print(f"  firms with no division: {unplaced}")

    return {
        "updated_at": now.isoformat(),
        "source": "kobo",
        "total": len(rows),
        "divisions": div,
        "location": counts(rows, form, f["location"]),
        "reg_authority": counts(rows, form, f["reg_authority"]),
        "ownership": counts(rows, form, f["ownership"]),
        "production": counts(rows, form, f["production"]),
        "timeline": {"dates": [d.isoformat() for d in dates], "counts": [per_day[d] for d in dates]},
    }


def main():
    which = (sys.argv[1] if len(sys.argv) > 1 else "census").lower()
    if which not in DATASETS:
        sys.exit(f"Unknown dataset '{which}'. Use: {', '.join(DATASETS)}")
    cfg = DATASETS[which]
    token = os.environ.get("KOBO_TOKEN" + cfg["env"]) or os.environ.get("KOBO_TOKEN")
    uid = os.environ.get("KOBO_ASSET_UID" + cfg["env"])
    server = (os.environ.get("KOBO_SERVER" + cfg["env"]) or os.environ.get("KOBO_SERVER") or "https://kf.kobotoolbox.org").rstrip("/")
    if not token or not uid:
        print(f"[{which}] KOBO_TOKEN / KOBO_ASSET_UID{cfg['env']} not set, skipping.")
        return

    asset, rows = fetch_all(server, uid, token)
    print(f"[{which}] fetched {len(rows)} submissions from {server}")
    data = aggregate(rows, Form(asset))
    out = os.path.join(os.path.dirname(__file__), "..", cfg["out"])
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print(f"[{which}] wrote {cfg['out']}: total {data['total']}, on map {sum(data['divisions'].values())}")
    for k in ("location", "reg_authority", "ownership", "production"):
        print(f"  {k}: {dict(zip(data[k]['labels']['en'], data[k]['values']))}")


if __name__ == "__main__":
    main()
