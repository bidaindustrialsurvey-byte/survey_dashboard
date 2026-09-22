"""Change a dashboard password.

Run:  python scripts/make_user.py
Pick the account, type the new password, then replace that account's hash
inside ACCOUNTS near the top of the <script> section in index.html.
"""
import getpass
import hashlib

ACCOUNTS = {"1": ("sanem", "SANEM"), "2": ("invest", "Invest Bangladesh")}
print("1) SANEM\n2) Invest Bangladesh")
choice = input("Which account? ").strip()
if choice not in ACCOUNTS:
    raise SystemExit("Type 1 or 2.")
user, name = ACCOUNTS[choice]
pw = getpass.getpass(f"New password for {name}: ")
h = hashlib.sha256(f"{user}:{pw}:soi-bd".encode("utf-8")).hexdigest()
print(f"\nIn index.html, replace the hash on the '{user}:' line with:\n{h}")
