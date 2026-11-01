"""Install the project's hook without overwriting an existing custom hook."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
hook = Path(subprocess.check_output(["git", "rev-parse", "--git-path", "hooks/pre-commit"], cwd=root, text=True).strip())
if not hook.is_absolute():
    hook = root / hook
content = '#!/bin/sh\nset -eu\nexec ./scripts/check-privacy.sh\n'
if hook.exists() and hook.read_text() != content:
    raise SystemExit("Existing pre-commit hook preserved; integrate scripts/check-privacy.sh manually.")
hook.parent.mkdir(parents=True, exist_ok=True)
hook.write_text(content)
hook.chmod(0o755)
(root / "scripts/check-privacy.sh").chmod(0o755)
print("Privacy pre-commit hook installed.")
