"""Scan Git's staged blobs, including force-added ignored files; never echo a match."""
import base64
import re
import subprocess
import sys
from pathlib import PurePosixPath

# Encoded so the guard can inspect its own staged source without false positives.
DENIED = [base64.b64decode(x).decode() for x in (
    "U01BTiA0Nw==", "aXZhbndhbGRlbg==", "Rk9STklLQQ==", "ODcuOQ==",
)]
PATTERN = re.compile("|".join(re.escape(x) for x in DENIED), re.I)


def violation(path, content):
    parts = PurePosixPath(path).parts
    if "private" in parts or ".local." in path or any(p.startswith(".env") and p != ".env.example" for p in parts):
        return "private path"
    if b"\0" in content:
        return "binary staged file requires review"
    value = content.decode("utf-8", errors="replace")
    if PATTERN.search(value) or re.search(r"(?:calendar/event\?eid=|drive\.google\.com/drive/folders/|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)", value, re.I):
        return "personal identifier, private link, or credential"
    return None


def main():
    paths = subprocess.check_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]).split(b"\0")
    errors = []
    for raw in filter(None, paths):
        path = raw.decode("utf-8")
        content = subprocess.check_output(["git", "show", f":{path}"])
        if reason := violation(path, content):
            errors.append((path, reason))
    if errors:
        for path, reason in errors:
            print(f"Privacy guard blocked {path!r}: {reason}.", file=sys.stderr)
        print("Unstage the file and keep sensitive data in the ignored vault. No matching content was printed.", file=sys.stderr)
        return 1
    print(f"Privacy guard: {len(list(filter(None, paths)))} staged files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
