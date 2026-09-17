"""Change the dashboard password.

Run:  python scripts/make_user.py
Then replace the hash inside ACCOUNT near the top of the <script> section in index.html.
"""
import getpass
import hashlib

pw = getpass.getpass("New password for the SANEM account: ")
h = hashlib.sha256(f"sanem:{pw}:soi-bd".encode("utf-8")).hexdigest()
print()
print(f"  const ACCOUNT = {{ u:'sanem', hash:'{h}' }};")
