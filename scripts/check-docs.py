"""Catch broken local targets in the portable repository handoff documents."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = [ROOT / name for name in ("AGENTS.md", "PRODUCT.md", "README.md")]
DOCUMENTS += sorted((ROOT / "docs").glob("*.md"))
errors = []
checked = 0

for document in DOCUMENTS:
    # Handoff docs use inline Markdown links; code samples are not links.
    content = re.sub(r"```.*?```", "", document.read_text(), flags=re.DOTALL)
    for destination in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", content):
        destination = destination.strip().strip("<>")
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        checked += 1
        target = document.parent / unquote(parsed.path)
        if parsed.path.startswith("/") or not target.resolve().is_relative_to(ROOT):
            errors.append(f"{document.relative_to(ROOT)}: use a repository-relative link: {destination}")
        elif not target.exists():
            errors.append(f"{document.relative_to(ROOT)}: missing target: {destination}")

if errors:
    raise SystemExit("\n".join(errors))
print(f"Documentation links: {checked} local targets checked in {len(DOCUMENTS)} files (anchors not checked).")
