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
secrets = []
config = root / "private/schola.local.json"
if config.exists():
    local = json.loads(config.read_text())
    secrets = [local.get("llm", {}).get("apiKey"), local.get("search", {}).get("apiKey"),
               local.get("access", {}).get("sessionSecret"), local.get("access", {}).get("passwordHash")]
    secrets = [s for s in secrets if isinstance(s, str) and len(s) >= 12]
for directory in (build / "static", build / "server"):
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in (".js", ".json", ".html", ".map", ".txt", ".rsc"):
            count += 1
            content = path.read_text(errors="replace")
            if any(secret in content or json.dumps(secret)[1:-1] in content for secret in secrets):
                raise SystemExit("A configured secret appeared in emitted production code; content withheld")
            if privacy.PATTERN.search(content):
                raise SystemExit(f"Private identifier found in emitted file {path.relative_to(build)}; content withheld")
for path in build.rglob("*.nft.json"):
    if "dev" in path.relative_to(build).parts:
        continue
    for entry in json.loads(path.read_text()).get("files", []):
        resolved = (path.parent / entry).resolve()
        if resolved.is_relative_to((root / "private").resolve()) or ".local." in resolved.name or resolved.name.startswith(".env"):
            raise SystemExit("A private path was included in the production file trace")
print(f"Production privacy check: {count} emitted text files inspected; no seed identifiers or private traced files.")
