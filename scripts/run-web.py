"""Launch Next on loopback with the runtime-only local configuration path."""
import os
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
command = sys.argv[1] if len(sys.argv) == 2 else ""
if command not in ("dev", "start"):
    raise SystemExit("Usage: python3 scripts/run-web.py dev|start")
os.chdir(root)
env = {**os.environ, "STUDAB27_CONFIG_PATH": str(root / "private/schola.local.json"), "NEXT_TELEMETRY_DISABLED": "1",
       "NODE_ENV": "development" if command == "dev" else "production"}
node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required")
os.execve(node, [node, str(root / "node_modules/next/dist/bin/next"), command, "--hostname", "127.0.0.1", "--port", "3270"], env)
