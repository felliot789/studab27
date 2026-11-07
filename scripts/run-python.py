"""Launch this interpreter with StudAb27's verified app-only SQLite library."""
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from schola.sqlite_runtime import runtime_environment

if not sys.argv[1:]:
    raise SystemExit('Usage: python scripts/run-python.py -m MODULE [arguments]')
env = runtime_environment(root, required=os.environ.get('STUDAB27_REQUIRE_SQLITE_RUNTIME') == '1')
os.chdir(root)
os.execve(sys.executable, [sys.executable, *sys.argv[1:]], env)
