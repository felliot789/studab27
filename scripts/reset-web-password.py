"""Rotate the local workspace login and invalidate all existing sessions."""
import hashlib
import json
import os
from pathlib import Path
import secrets

os.umask(0o077)
vault = Path(__file__).resolve().parents[1] / "private"
path = vault / "schola.local.json"
config = json.loads(path.read_text())
password, salt = secrets.token_urlsafe(24), secrets.token_hex(16)
config["access"].update({"passwordSalt": salt, "passwordHash": hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024).hex(), "sessionSecret": secrets.token_hex(32)})
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps(config, indent=2) + "\n")
temporary.chmod(0o600)
temporary.replace(path)
target = vault / "web-login.local.txt"
target.write_text("StudAb27 workspace password\n" + password + "\n\nRotated locally. Existing browser sessions are no longer valid.\n")
target.chmod(0o600)
print("Password rotated. Read private/web-login.local.txt locally; no secret was printed.")
