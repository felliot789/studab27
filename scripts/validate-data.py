"""Validate the public research catalogue; no private files are read."""
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
data = root / "data/public"
routes = json.loads((data / "scholarships_2027.json").read_text())
ids = {r["id"] for r in routes}
assert routes and len(routes) == len(ids), "Catalogue routes must have unique IDs"
for r in routes:
    assert r["seedStatus"] == "REVIEWED_DRAFT_NOT_ELIGIBILITY_VERIFICATION"
    assert "originalResearchRecord" not in r
    for field in ("officialSourceUrl", "secondarySourceUrl"):
        if r[field]:
            url = urlsplit(r[field])
            assert url.scheme in ("https", "http") and url.hostname and not url.username
overlays = json.loads((data / "overlay.example.json").read_text())
assert len(overlays) == len(ids) and {o["routeId"] for o in overlays} == ids
tasks = json.loads((data / "tasks.json").read_text())
assert len({t["id"] for t in tasks}) == len(tasks)
assert all(0 < t["minutes"] <= 15 and set(t["routeIds"]) <= ids for t in tasks)
assert len(json.loads((data / "bricks.json").read_text())) == 4
for note in json.loads((data / "source_verifications.json").read_text()):
    assert not note.get("routeId") or note["routeId"] in ids
outlooks = json.loads((data / "scholarship_outlooks.json").read_text())
assert set(outlooks) <= ids
for outlook in outlooks.values():
    assert outlook["category"] in ("REALISTIC", "REACH", "LOTTERY", "UNKNOWN")
    assert outlook["reason"].strip() and outlook["scope"].strip() and outlook["evidence"]
    date.fromisoformat(outlook["reviewedAt"])
    for evidence in outlook["evidence"]:
        url = urlsplit(evidence["url"])
        assert url.scheme == "https" and url.hostname and not url.username and not url.password
        assert evidence["finding"].strip()
        date.fromisoformat(evidence["checkedAt"])
    if rate := outlook.get("publishedRate"):
        assert rate["outcome"] == "SCHOLARSHIP_AWARDED"
        assert rate["applicantStage"] == "ALL_APPLICANTS"
        assert rate["cycle"].strip() and rate["population"].strip()
        assert type(rate["applicants"]) is int and type(rate["recipients"]) is int
        assert 0 <= rate["recipients"] <= rate["applicants"] and rate["applicants"] > 0
        assert rate["sourceUrl"] in {e["url"] for e in outlook["evidence"]}
guides = json.loads((data / "application_guides.json").read_text())
assert set(guides) <= ids
brick_keys = {f"{brick['id']}:{item['id']}" for brick in json.loads((data / "bricks.json").read_text()) for item in brick["items"]}
for guide in guides.values():
    assert guide["cycle"] == "2027 entry" and guide["summary"].strip()
    date.fromisoformat(guide["reviewedAt"])
    sources = {s["id"] for s in guide["sources"]}
    assert len(sources) == len(guide["sources"])
    for source in guide["sources"]:
        url = urlsplit(source["url"])
        assert url.scheme == "https" and url.hostname and not url.username and not url.password
        assert source["scope"].strip() and source["title"].strip()
    assert len({s["id"] for s in guide["sections"]}) == len(guide["sections"])
    items = [item for section in guide["sections"] for item in section["items"]]
    assert items and len({i["id"] for i in items}) == len(items)
    for item in items:
        assert item["title"].strip() and item["detail"].strip()
        assert item["kind"] in ("DOCUMENT", "TASK")
        assert item["basis"] in ("CURRENT", "GENERAL", "RECHECK")
        assert item["sourceIds"] and set(item["sourceIds"]) <= sources
        assert "optional" not in item or type(item["optional"]) is bool
        assert "sharedKey" not in item or item["sharedKey"] in brick_keys
events = json.loads((data / "calendar_events.json").read_text())
event_ids = {e["id"] for e in events}
assert events and len(events) == len(event_ids), "Calendar events must have unique IDs"
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
encoded = json.dumps([routes, events, outlooks, guides])
for private_key in ("snapshotSha256", '"snapshot":', "originalResearchRecord", "sources/003.txt", "/home/elliot/"):
    assert private_key not in encoded, "Private review artifacts must remain outside public data"
print(f"Public data: {len(routes)} routes, {len(events)} evidence-scoped events, {len(outlooks)} scoped scholarship outlooks, {len(guides)} source-scoped application guides, aligned fictional overlays, 4 document packs, bounded atomic tasks.")
