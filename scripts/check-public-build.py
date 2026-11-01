"""Check emitted production code and file traces for private seed contamination."""
import importlib.util
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("privacy", root / "scripts/privacy_guard.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)
build = root / ".next"
if not (build / "BUILD_ID").exists():
    raise SystemExit("Run npm run build first")
count = 0
for directory in (build / "static", build / "server"):
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in (".js", ".json", ".html", ".map", ".txt", ".rsc"):
            count += 1
            if privacy.PATTERN.search(path.read_text(errors="replace")):
                raise SystemExit(f"Private identifier found in emitted file {path.relative_to(build)}; content withheld")
for path in build.rglob("*.nft.json"):
    if "dev" in path.relative_to(build).parts:
        continue
    for entry in json.loads(path.read_text()).get("files", []):
        resolved = (path.parent / entry).resolve()
        if resolved.is_relative_to((root / "private").resolve()) or ".local." in resolved.name:
            raise SystemExit("A private path was included in the production file trace")
print(f"Production privacy check: {count} emitted text files inspected; no seed identifiers or private traced files.")
