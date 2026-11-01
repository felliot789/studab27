"""Install an optional 12-hour user timer. No root, linger, or cloud access."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--enable", action="store_true", help="Explicitly enable the prepared timer")
args = parser.parse_args()

def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'

units = Path.home() / ".config/systemd/user"
units.mkdir(parents=True, exist_ok=True)
service = f"""[Unit]
Description=StudAb27 official scholarship source scan
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={str(root).replace('%', '%%')}
ExecStart={quote(sys.executable)} -m schola.watcher
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
NoNewPrivileges=true
TimeoutStartSec=25min
"""
timer = """[Unit]
Description=Check StudAb27 scholarship sources every twelve hours

[Timer]
OnCalendar=*-*-* 00,12:17:00 UTC
Persistent=true
RandomizedDelaySec=5min
Unit=studab27-watchtower.service

[Install]
WantedBy=timers.target
"""
for name, content in (("studab27-watchtower.service", service), ("studab27-watchtower.timer", timer)):
    target = units / name
    if target.exists() and target.read_text() != content:
        raise SystemExit(f"Existing {name} differs and was preserved; review before replacing it")
    target.write_text(content)
env = dict(os.environ)
env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={env['XDG_RUNTIME_DIR']}/bus")
subprocess.run(["systemctl", "--user", "daemon-reload"], env=env, check=True)
if args.enable:
    subprocess.run(["systemctl", "--user", "enable", "--now", "studab27-watchtower.timer"], env=env, check=True)
    print("12-hour user timer enabled. It runs while the user manager is available; it cannot wake a powered-off host.")
else:
    print("Timer prepared but not enabled. Run with --enable when continuous local monitoring is wanted.")
