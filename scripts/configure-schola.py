"""Import the owner's .env once; thereafter edit private/schola.local.json.

Does not print credentials, overwrite existing settings, or change the source .env.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--from-env", action="store_true", required=True)
parser.add_argument("--allow-context", action="store_true")
parser.add_argument("--origin", action="append", default=[])
args = parser.parse_args()
vault = root / "private"
vault.mkdir(exist_ok=True, mode=0o700)
vault.chmod(0o700)
target = vault / "schola.local.json"
if target.exists() or (vault / "web-login.local.txt").exists():
    raise SystemExit("Existing Schola configuration preserved. Edit private/schola.local.json directly.")
values = {}
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    key, sep, value = line.removeprefix("export ").partition("=")
    if sep:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
required = ("INFERENCE_BASE_URL", "INFERENCE_API_KEY", "INFERENCE_MODEL")
if any(not values.get(key) for key in required):
    raise SystemExit("The .env is missing a required INFERENCE setting; no configuration written.")
password = secrets.token_urlsafe(24)
salt = secrets.token_hex(16)
config = {
    "version": 1,
    "contextAllowed": args.allow_context,
    "llm": {"baseUrl": values[required[0]].rstrip("/"), "apiKey": values[required[1]], "model": values[required[2]],
            "toolMode": "json", "timeoutSeconds": 120, "maxOutputTokens": 1600, "maxToolRounds": 6, "dailyCallLimit": 80},
    "search": {"provider": "searxng", "baseUrl": "http://127.0.0.1:8080", "apiKey": "", "maxResults": 5},
    "background": {"enabled": True, "maxJobsPerDay": 3},
    "access": {"enabled": True, "origins": ["http://127.0.0.1:3270", "http://localhost:3270", *args.origin],
               "passwordSalt": salt, "passwordHash": hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024).hex(),
               "sessionSecret": secrets.token_hex(32), "sessionDays": 14},
}
for path, content in ((target, json.dumps(config, indent=2) + "\n"),
                      (vault / "web-login.local.txt", "StudAb27 workspace password\n" + password + "\n\nChange the password with scripts/reset-web-password.py. Never share this file.\n")):
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
        f.write(content)
(root / ".env").chmod(0o600)
print("Schola configured. Canonical settings: private/schola.local.json. Login password: private/web-login.local.txt. Secrets were not printed.")
