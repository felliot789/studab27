"""Small, stable tasks: no decisions, submissions, or generated application prose."""
import json
import sys
import hashlib
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from schola.evaluator import curriculum_gate, graduation_gate


def task_pool(payload):
    """Stable reusable steps; create no prose intended for an application."""
    tasks = [t for t in payload["tasks"] if not t.get("generated")]
    for brick in payload.get("bricks", []):
        for i, item in enumerate(brick["items"]):
            key = f'{brick["id"]}:{item["id"]}'
            tasks.append({"id": f'doc-{brick["id"]}-{item["id"]}', "generated": True, "brickKey": key, "brickId": brick["id"], "category": "DOC_BRICK_STEP", "title": item["label"], "description": f'Checklist step in {brick["folder"]}. Record unresolved items in the inbox.', "minutes": 15, "priority": 60 + i, "routeIds": [], "sources": [], "steps": ["Locate the current file or the person who can supply it.", "Record one missing detail or save the existing document in its pack.", "Mark the document checklist only when the step is complete."]})
    for route in payload["routes"]:
        for field, title in (("curriculum", "Check national-diploma direct entry"), ("graduation", "Find the final-document cutoff")):
            tasks.append({"id": f'rule-{field}-{route["id"]}', "generated": True, "gateField": field, "requiresInProgress": True, "category": "VERIFY_RULE", "title": f'{title} at {route["institution"]}', "description": "Open the exact engineering program’s current-cycle call. Record one sourced answer in the route’s checked-rule form; leave other fields unknown.", "minutes": 15, "priority": 30 if field == "curriculum" else 35, "routeIds": [route["id"]], "sources": [route["officialSourceUrl"]], "steps": ["Identify the exact program and 2027 entry cycle.", "Find the single rule named in this task and its official source.", "Record the answer and source in the route drawer."]})
    for milestone in payload.get("milestones", []):
        # Superseded imported UBC targets must not outrank the corrected official date.
        if "UBC" in milestone.get("title", "").upper():
            continue
        key = hashlib.sha256(f'{milestone["date"]}{milestone["title"]}'.encode()).hexdigest()[:16]
        tasks.append({"id": f"milestone-{key}", "generated": True, "milestoneDate": milestone["date"], "category": "DOC_BRICK_STEP", "title": f'Check one requirement: {milestone["title"]}', "description": "Imported planning milestone; this record does not verify an official deadline. Check the required documents and submission receipts.", "minutes": 15, "priority": 10, "routeIds": [], "sources": [], "steps": ["Open the saved milestone and the current official requirements.", "Locate one required document or submission receipt.", "Save the receipt or capture one specific missing item in the inbox."]})
    return tasks


def briefing(payload):
    state = payload.get("state", {})
    now = datetime.now(timezone.utc).isoformat()
    route_by_id = {r["id"]: r for r in payload["routes"]}
    overlays = {o["routeId"]: o for o in payload.get("overlays", [])}
    cards = []
    for card in payload["tasks"]:
        saved = state.get("tasks", {}).get(card["id"], {})
        if saved.get("status") == "DONE" or saved.get("snoozedUntil", "") > now:
            continue
        linked = [r for r in card.get("routeIds", []) if overlays.get(r, {}).get("applicationStatus") not in ("DROP", "SUBMITTED")]
        if card.get("requiresActiveRoute") and not linked:
            continue
        if card.get("brickKey") and state.get("bricks", {}).get(card["brickKey"]):
            continue
        if card.get("requiresInProgress"):
            overlay = overlays.get(card["routeIds"][0], {})
            if overlay.get("applicationStatus") not in ("RESEARCHING", "IN_PROGRESS"):
                continue
            evaluated = curriculum_gate(overlay) if card["gateField"] == "curriculum" else graduation_gate(overlay, payload["profile"])
            if evaluated["status"] != "UNKNOWN":
                continue
        if card.get("milestoneDate"):
            days = (date.fromisoformat(card["milestoneDate"]) - datetime.now(ZoneInfo("Asia/Jakarta")).date()).days
            if days < 0 or days > 7:
                continue
        sources = [route_by_id[r]["officialSourceUrl"] for r in linked if r in route_by_id]
        cards.append({**card, "sources": list(dict.fromkeys(card.get("sources", []) + sources)), "replacedAt": saved.get("replacedAt", "")})
    # Replacing moves a card behind remaining work without completing or losing it.
    cards.sort(key=lambda c: (bool(c["replacedAt"]), c["replacedAt"], c.get("priority", 100)))
    return {"cards": cards[:3], "remaining": len(cards), "completed": sum(t.get("status") == "DONE" for t in state.get("tasks", {}).values()), "taskTitles": {t["id"]: t["title"] for t in payload["tasks"] if "title" in t}}


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    json.dump(task_pool(payload) if payload.get("command") == "pool" else briefing(payload), sys.stdout)
