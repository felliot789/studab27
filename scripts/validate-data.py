"""Validate only the public seed; no private files are read."""
import json
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
data = root / "data/public"
routes = json.loads((data / "scholarships_2027.json").read_text())
ids = {r["id"] for r in routes}
assert len(routes) == len(ids) == 57, "Catalogue must contain 57 unique routes"
for r in routes:
    assert r["seedStatus"] == "UNVERIFIED_SEED"
    for field in ("officialSourceUrl", "secondarySourceUrl"):
        if r[field]:
            url = urlsplit(r[field])
            assert url.scheme in ("https", "http") and url.hostname and not url.username
overlays = json.loads((data / "overlay.example.json").read_text())
assert len(overlays) == 57 and {o["routeId"] for o in overlays} == ids
tasks = json.loads((data / "tasks.json").read_text())
assert len({t["id"] for t in tasks}) == len(tasks)
assert all(0 < t["minutes"] <= 15 and set(t["routeIds"]) <= ids for t in tasks)
assert len(json.loads((data / "bricks.json").read_text())) == 4
for note in json.loads((data / "source_verifications.json").read_text()):
    assert not note.get("routeId") or note["routeId"] in ids
print("Public data: 57 routes, aligned fictional overlays, 4 document packs, bounded atomic tasks.")
