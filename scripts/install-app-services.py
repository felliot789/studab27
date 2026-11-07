"""Prepare persistent loopback web and Schola worker user services."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--enable", action="store_true")
args = parser.parse_args()
if not (root / ".next/BUILD_ID").exists():
    raise SystemExit("Build and check the app before installing services.")
if not (root / "private/schola.local.json").exists():
    raise SystemExit("Configure Schola and login before installing services.")
config = json.loads((root / "private/schola.local.json").read_text())
worker_python = Path(sys.executable)
if config.get("llm", {}).get("researchRuntime") == "langgraph":
    worker_python = root / ".venv-research/bin/python"
    if not worker_python.exists():
        raise SystemExit("Install requirements-research.txt in .venv-research before enabling the research worker.")

def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'

node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required.")
units = Path.home() / ".config/systemd/user"
units.mkdir(parents=True, exist_ok=True)
commands = {
    "studab27-web.service": ("StudAb27 private scholarship workspace", f'{quote(sys.executable)} {quote(root / "scripts/run-web.py")} start'),
    "studab27-schola.service": ("StudAb27 Schola conversation and source-review worker", f"{quote(worker_python)} -m schola.assistant worker"),
}
for name, (description, command) in commands.items():
    content = f"""[Unit]
Description={description}
After=network-online.target

[Service]
Type=simple
WorkingDirectory={str(root).replace('%', '%%')}
ExecStart={command}
Environment=NODE_ENV=production
Environment=NEXT_TELEMETRY_DISABLED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=SCHOLA_PYTHON={quote(sys.executable)}
UMask=0077
NoNewPrivileges=true
Restart=on-failure
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=default.target
"""
    target = units / name
    if target.exists() and target.read_text() != content:
        raise SystemExit(f"Existing {name} differs and was preserved. Review it locally before replacing.")
    target.write_text(content)
env = {**os.environ, "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}", "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{os.getuid()}/bus"}
subprocess.run(["systemctl", "--user", "daemon-reload"], env=env, check=True)
if args.enable:
    subprocess.run(["systemctl", "--user", "enable", "--now", *commands], env=env, check=True)
    print("StudAb27 web and Schola worker enabled. Web binds only to 127.0.0.1:3270; no public route was changed.")
else:
    print("Services prepared. Run with --enable to keep the web app and worker available.")
