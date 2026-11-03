"""Validate the public research catalogue; no private files are read."""
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
data = root / "data/public"
routes = json.loads((data / "scholarships_2027.json").read_text())
ids = {r["id"] for r in routes}
assert len(routes) == len(ids) == 57, "Catalogue must contain 57 unique routes"
for r in routes:
    assert r["seedStatus"] == "REVIEWED_DRAFT_NOT_ELIGIBILITY_VERIFICATION"
    assert "originalResearchRecord" not in r
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
events = json.loads((data / "calendar_events.json").read_text())
event_ids = {e["id"] for e in events}
assert len(events) == len(event_ids) == 174
for e in events:
    assert e["routeId"] in ids
    assert set(e["prerequisiteEventIds"]) <= event_ids
    assert all(next(p for p in events if p["id"] == pid)["routeId"] == e["routeId"] for pid in e["prerequisiteEventIds"])
    supported = e["sourceReview"]["status"] == "SOURCE_SUPPORTED_FOR_TARGET_CYCLE"
    assert e["calendarDateSupported"] == supported
    assert bool(e["date"]) == supported
    assert e["humanVerified"] is False
    if not supported:
        assert e["time"] is None and e["deadlineAtWib"] is None
    if e["deadlineAtWib"]:
        assert e["time"] and e["timezone"] and e["deadlineAtWib"].endswith("+07:00")
        datetime.fromisoformat(e["deadlineAtWib"])
    if e["date"]:
        date.fromisoformat(e["date"])
    if e.get("endDate"):
        assert e["endDate"] >= e["date"]
        date.fromisoformat(e["endDate"])
    for source in [e["sourceUrl"], *(s["url"] for s in e["sourceReview"]["evidence"])]:
        url = urlsplit(source)
        assert url.scheme in ("https", "http") and url.hostname and not url.username and not url.password
    assert "originalClaim" not in e
encoded = json.dumps([routes, events])
for private_key in ("snapshotSha256", '"snapshot":', "originalResearchRecord", "sources/003.txt", "/home/elliot/"):
    assert private_key not in encoded, "Private review artifacts must remain outside public data"
print("Public data: 57 routes, 174 evidence-scoped events, aligned fictional overlays, 4 document packs, bounded atomic tasks.")
