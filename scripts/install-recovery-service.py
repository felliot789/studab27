"""Prepare a daily local recovery user timer; starting it requires --enable."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def units_for(root, interpreter):
    service = f"""[Unit]
Description=StudAb27 verified complete local recovery snapshot

[Service]
Type=oneshot
WorkingDirectory={str(root).replace("%", "%%")}
ExecStart={quote(interpreter)} {quote(root / 'scripts/run-python.py')} -m schola.recovery create --keep 14
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=STUDAB27_REQUIRE_SQLITE_RUNTIME=1
UMask=0077
NoNewPrivileges=true
TimeoutStartSec=30min
Nice=10
IOSchedulingClass=idle
"""
    timer = """[Unit]
Description=Create StudAb27 local recovery snapshots daily

[Timer]
OnCalendar=*-*-* 03:17:00 Asia/Jakarta
Persistent=true
RandomizedDelaySec=10min
Unit=studab27-recovery.service

[Install]
WantedBy=timers.target
"""
    return {"studab27-recovery.service": service, "studab27-recovery.timer": timer}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable", action="store_true", help="Explicitly enable and start the daily timer")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    interpreter = root / ".venv-research/bin/python"
    if not interpreter.exists():
        interpreter = Path(sys.executable)
    if not (root / "scripts/run-python.py").is_file():
        parser.error("The app Python runtime wrapper must be installed first")
    directory = Path.home() / ".config/systemd/user"
    directory.mkdir(parents=True, exist_ok=True)
    units = units_for(root, interpreter)
    # Validate both targets before writing either so a conflict preserves all units.
    for name, content in units.items():
        target = directory / name
        if target.is_symlink() or (target.exists() and target.read_text() != content):
            parser.error(f"Existing {name} differs and was preserved; review it locally")
    for name, content in units.items():
        target = directory / name
        target.write_text(content)
        target.chmod(0o600)
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={env['XDG_RUNTIME_DIR']}/bus")
    subprocess.run(["systemctl", "--user", "daemon-reload"], env=env, check=True)
    if args.enable:
        subprocess.run(["systemctl", "--user", "enable", "--now", "studab27-recovery.timer"], env=env, check=True)
        print("Daily local recovery timer enabled. Off-device recovery remains unconfigured.")
    else:
        print("Daily local recovery timer prepared but not enabled. Use --enable to start it.")


if __name__ == "__main__":
    main()
