"""Production HTTP smoke check in a temporary fictional workspace.

Exercises persistence and recovery without touching the owner's vault.
"""
import json
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="studab27-app-check-") as directory:
        scratch = Path(directory)
        for name in (".next", "node_modules", "schola", "public"):
            (scratch / name).symlink_to(root / name, target_is_directory=True)
        shutil.copytree(root / "data", scratch / "data")
        expected_routes = {r["id"] for r in json.loads((scratch / "data/public/scholarships_2027.json").read_text())}
        calendar_path = scratch / "data/public/calendar_events.json"
        events = json.loads(calendar_path.read_text())
        source_notes = json.loads((scratch / "data/public/source_verifications.json").read_text())
        # This fictional copy exercises a prerequisite outside the selected route.
        selected_event = next(e for e in events if e["prerequisiteEventIds"] and any(n.get("routeId") == e["routeId"] for n in source_notes))
        scoped_route_id = selected_event["routeId"]
        cross_route_event = next(e for e in events if e["routeId"] != scoped_route_id)
        selected_event["prerequisiteEventIds"].append(cross_route_event["id"])
        calendar_path.write_text(json.dumps(events))
        expected_events = {e["id"] for e in events}
        shutil.copy(root / "package.json", scratch / "package.json")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        last_headers = {}

        def request(route="/api/schola", value=None, headers=None, expect=200):
            h = {"Origin": origin, **(headers or {})}
            if value is not None: h["Content-Type"] = "application/json"
            req = Request(origin + route, data=None if value is None else json.dumps(value).encode(), headers=h)
            try:
                with urlopen(req, timeout=30) as response:
                    status, content, response_headers = response.status, response.read(), response.headers
            except HTTPError as e:
                status, content, response_headers = e.code, e.read(), e.headers
            assert status == expect, (route, status, content[:200])
            last_headers.clear()
            last_headers.update({k.lower(): v for k, v in response_headers.items()})
            return json.loads(content) if "application/json" in response_headers.get("Content-Type", "") else content

        server_env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "STUDAB27_DEMO": "0", "STUDAB27_CONFIG_PATH": str(scratch / "private/schola.local.json")}
        evaluator = os.environ.get("STUDAB27_EVALUATOR_BIN")
        if evaluator:
            # Prove that the selected backend is used and failures do not fall back.
            wrapper = scratch / "evaluator-check"
            wrapper.write_text(f'''#!{sys.executable}
from pathlib import Path
import os
import sys
directory = Path(__file__).parent
(directory / "evaluator-used").touch()
if (directory / "evaluator-fail").exists():
    print("FICTIONAL_BACKEND_DIAGNOSTIC", file=sys.stderr)
    raise SystemExit(1)
if (directory / "evaluator-invalid").exists():
    print("FICTIONAL_INVALID_OUTPUT")
    raise SystemExit(0)
os.execv({evaluator!r}, [{evaluator!r}])
''')
            wrapper.chmod(0o700)
            server_env["STUDAB27_EVALUATOR_BIN"] = str(wrapper)
        log = (scratch / "server.log").open("w")
        server = subprocess.Popen(["node", str(root / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(port)], cwd=scratch, stdout=log, stderr=subprocess.STDOUT, env=server_env)
        try:
            for attempt in range(80):
                if server.poll() is not None: raise AssertionError("Temporary app server exited")
                try:
                    with urlopen(origin, timeout=1) as response:
                        if response.status == 200: break
                except (OSError, TimeoutError): time.sleep(.15)
            else: raise AssertionError("Temporary app server did not become ready")
            data = request()
            assert data["mode"] == "DEMO" and len(data["briefing"]["cards"]) == 3
            assert {r["id"] for r in data["routes"]} == expected_routes
            assert {e["id"] for e in data["calendarEvents"]} == expected_events
            request("/api/schola?view=not-a-view", expect=400)
            request("/api/schola?view=", expect=400)
            request("/api/schola?view=detail", expect=400)
            request("/api/schola?view=detail&routeId=not-a-route", expect=404)
            detail = request("/api/schola?view=detail&routeId=" + quote(scoped_route_id))
            assert detail["routes"] == [r for r in data["routes"] if r["id"] == scoped_route_id]
            assert detail["overlays"] == [o for o in data["overlays"] if o["routeId"] == scoped_route_id]
            assert detail["evaluations"] == [e for e in data["evaluations"] if e["routeId"] == scoped_route_id]
            assert detail["sourceNotes"] == [n for n in data["sourceNotes"] if n.get("routeId") == scoped_route_id]
            selected_events = [e for e in data["calendarEvents"] if e["routeId"] == scoped_route_id]
            event_ids = {e["id"] for e in selected_events} | {p for e in selected_events for p in e["prerequisiteEventIds"]}
            assert detail["calendarEvents"] == [e for e in data["calendarEvents"] if e["id"] in event_ids]
            assert cross_route_event in detail["calendarEvents"]
            assert detail["profile"] == data["profile"] and detail["bricks"] == data["bricks"]
            assert len(json.dumps(detail)) < len(json.dumps(data)) / 2
            assert {r["id"] for r in request()["routes"]} == expected_routes
            scholarship_api = "/api/schola/scholarships"
            assert request(scholarship_api) == {"drafts": [], "mode": "DEMO"}
            request(scholarship_api, {"action": "start", "id": str(uuid.uuid4()), "query": "Fictional scholarship"}, expect=400)
            assert request(scholarship_api)["drafts"] == []
            for route in ("/", "/scholarships", "/scholarships?browse=1", "/today", "/applications", "/calendar", "/documents", "/documents?tab=reusable", "/updates", "/settings", "/catalogue", "/bricks", "/watchtower", "/schola", "/login"): request(route)
            for route in data["routes"]:
                request("/scholarships/" + quote(route["id"]))
            # Next's streamed notFound response retains HTTP 200 after streaming
            # starts; verify that it renders recovery UI rather than a route.
            missing = request("/scholarships/not-a-route")
            assert "Page not found".encode() in missing
            # Reading the refreshed catalogue/calendar must not change personal state.
            assert request()["overlays"] == data["overlays"]
            assert request()["state"] == data["state"]
            focused_calendar = request("/calendar?route=" + quote(data["routes"][0]["id"]))
            assert b"All routes" in focused_calendar
            request(value={"action": "task", "id": "sat-registration", "command": "done"})
            assert request()["state"]["tasks"]["sat-registration"]["status"] == "DONE"
            request(value={"action": "task", "id": "sat-registration", "command": "undo"})
            request(value={"action": "brick", "key": "profile:sat-ticket", "done": True})
            assert request()["state"]["bricks"]["profile:sat-ticket"]
            rid = data["routes"][0]["id"]
            description = request("/scholarships/" + quote(rid) + "?tab=overview")
            assert b"About this scholarship" in description and b"Ask about this scholarship" in description
            original_overlay = data["overlays"][0]
            request(value={"action": "overlay", "id": rid, "patch": {"saved": True}})
            assert request()["overlays"][0] == {**original_overlay, "saved": True}
            request(value={"action": "overlay", "id": rid, "patch": {"saved": "yes"}}, expect=400)
            assert request()["overlays"][0]["saved"] is True
            request(value={"action": "overlay", "id": rid, "patch": {"applicationStatus": "RESEARCHING", "notes": "Fictional persistence check"}})
            assert request()["overlays"][0]["applicationStatus"] == "RESEARCHING" and request()["overlays"][0]["saved"]
            # A guide's progress is independent from reusable documents and priority.
            guided = [r for r in data["routes"] if r.get("applicationGuide")]
            guide_route = guided[0]
            guide_id = guide_route["id"]
            items = [i for s in guide_route["applicationGuide"]["sections"] for i in s["items"]]
            step = next(i for i in items if not i.get("optional"))
            request(value={"action": "tracking", "id": guide_id, "command": "add"})
            plan = lambda route_id: next(o for o in request()["overlays"] if o["routeId"] == route_id)
            assert plan(guide_id)["tracked"] and "pursuitLevel" not in plan(guide_id)
            request(value={"action": "requirement", "routeId": guide_id, "id": step["id"], "status": "DOING", "note": "Fictional checklist note"})
            request(value={"action": "requirement", "routeId": guide_id, "id": step["id"], "status": "DONE"})
            progress = request()["state"]["requirements"]
            assert progress[guide_id][step["id"]]["note"] == "Fictional checklist note"
            assert progress[guide_id][step["id"]]["status"] == "DONE"
            assert guided[1]["id"] not in progress
            for change in ({"status": "AUTOMATIC"}, {"status": ["DONE"]}, {"status": "NOT_NEEDED"}, {"id": "not-a-step"}, {"note": "x" * 2001}):
                request(value={"action": "requirement", "routeId": guide_id, "id": step["id"], "status": "DONE", **change}, expect=400)
                assert request()["state"]["requirements"] == progress
            request(value={"action": "tracking", "id": guide_id, "command": "main"})
            assert plan(guide_id)["mainTarget"] and plan(guide_id)["pursuitLevel"] == "FOCUS"
            request(value={"action": "tracking", "id": guided[1]["id"], "command": "main"})
            assert not plan(guide_id)["mainTarget"]
            request(value={"action": "overlay", "id": guided[1]["id"], "patch": {"pursuitLevel": None}})
            assert not plan(guided[1]["id"])["mainTarget"] and "pursuitLevel" not in plan(guided[1]["id"])
            request(value={"action": "overlay", "id": guide_id, "patch": {"pursuitLevel": "BACKUP"}})
            request(value={"action": "tracking", "id": guide_id, "command": "remove"})
            assert not plan(guide_id)["tracked"] and request()["state"]["requirements"] == progress
            request(value={"action": "tracking", "id": guide_id, "command": "add"})
            assert plan(guide_id)["pursuitLevel"] == "BACKUP" and request()["state"]["requirements"] == progress
            request(value={"action": "overlay", "id": guide_id, "patch": {"pursuitLevel": "LOTTERY"}}, expect=400)
            request(value={"action": "overlay", "id": guide_id, "patch": {"pursuitLevel": ["FOCUS"]}}, expect=400)
            request(value={"action": "inbox", "text": "Fictional test capture; never fetch this automatically."})
            inbox = request()["inbox"]
            request(value={"action": "triage", "id": inbox[0]["id"], "status": "TRIAGED"})
            assert request()["inbox"][0]["status"] == "TRIAGED"
            before_scenario = request()
            scenario = request(value={"action": "simulate", "sat": 1560, "cap": 8})
            assert {e["routeId"] for e in scenario["evaluations"]} == expected_routes
            expected_scenario = subprocess.run([sys.executable, "-m", "schola.evaluator"], cwd=root,
                input=json.dumps({**{key: before_scenario[key] for key in ("routes", "overlays", "profile")}, "sat": 1560, "cap": 8}),
                text=True, capture_output=True, check=True, timeout=15)
            assert scenario["evaluations"] == json.loads(expected_scenario.stdout), "Scenario backend differs from the reference"
            after_scenario = request()
            for key in ("profile", "overlays", "state", "milestones", "inbox"):
                assert after_scenario[key] == before_scenario[key], "Read-only scenario changed workspace data"
            assert after_scenario["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] == 5
            if evaluator:
                assert (scratch / "evaluator-used").exists(), "Selected scenario backend was not used"
                for flag in ("evaluator-fail", "evaluator-invalid"):
                    failure_flag = scratch / flag
                    failure_flag.touch()
                    failure = request(value={"action": "simulate", "sat": 1560, "cap": 8}, expect=400)
                    assert "error" in failure and "FICTIONAL" not in failure["error"]
                    failure_flag.unlink()
                assert request(value={"action": "simulate", "sat": 1560, "cap": 8}) == scenario
                after_failure = request()
                for key in ("profile", "overlays", "state", "milestones", "inbox"):
                    assert after_failure[key] == before_scenario[key], "Failed evaluator changed workspace data"
            request(value={"action": "simulate", "sat": 900, "cap": 8}, expect=400)
            request(value={"action": "task", "id": "sat-registration", "command": "done"}, headers={"Origin": "https://example.com"}, expect=403)
            request(headers={"Host": "example.com"}, expect=403)
            bundle = request("/api/schola/export")
            assert bundle["format"] == "studab27-v1" and bundle["mode"] == "DEMO"
            bundle["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] = 6
            request(value={"action": "import", "bundle": bundle})
            assert request()["mode"] == "PRIVATE" and request()["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] == 6
            assert request()["overlays"][0]["saved"] is True
            assert request()["state"]["requirements"] == progress
            bad_progress = json.loads(json.dumps(bundle))
            bad_progress["state"]["requirements"][guide_id][step["id"]]["status"] = "AUTOMATIC"
            request(value={"action": "import", "bundle": bad_progress}, expect=400)
            assert request()["state"]["requirements"] == progress
            assert list((scratch / "private/backups").glob("*.local.json"))
            bad = {**bundle, "overlays": [*bundle["overlays"], bundle["overlays"][0]]}
            request(value={"action": "import", "bundle": bad}, expect=400)
            assert request()["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] == 6
            # No model is configured: a failed enqueue must still preserve the
            # lead, which can be reviewed manually without any network traffic.
            draft_id = str(uuid.uuid4())
            lead = {"action": "start", "id": draft_id, "query": "Fictional HTTP engineering award for 2027",
                    "sourceUrl": "https://university.edu/fixture"}
            request(scholarship_api, lead, expect=400)
            draft_list = request(scholarship_api)
            assert draft_list["mode"] == "PRIVATE" and len(draft_list["drafts"]) == 1
            failed = draft_list["drafts"][0]
            assert failed["id"] == draft_id and failed["status"] == "FAILED" and failed["query"] == lead["query"]
            assert failed["fields"]["officialSourceUrl"] == lead["sourceUrl"] and failed["error"]
            request(scholarship_api, {"action": "retry", "id": draft_id, "revision": failed["revision"]}, expect=400)
            retried = request(scholarship_api)["drafts"][0]
            assert retried["status"] == "FAILED" and retried["jobId"] != failed["jobId"] and retried["fields"] == failed["fields"]
            failed = retried
            fields = {**failed["fields"], "country": "Australia", "institution": "Fictional HTTP University",
                      "scholarshipName": "Fictional HTTP Engineering Award", "benefitsCoverage": "Tuition support; living costs UNKNOWN",
                      "unresolvedQuestions": ["2027 entry and Indonesian eligibility remain UNKNOWN"]}
            ready = request(scholarship_api, {"action": "save", "id": draft_id, "revision": failed["revision"], "fields": fields})["draft"]
            assert ready["status"] == "READY" and ready["fields"] == fields
            before_conflict = request()["state"]
            request(scholarship_api, {"action": "save", "id": draft_id, "revision": failed["revision"], "fields": fields}, expect=409)
            assert request()["state"] == before_conflict
            assert {r["id"] for r in request()["routes"]} == expected_routes
            accept = {"action": "accept", "id": draft_id, "revision": ready["revision"], "fields": fields}
            accepted = request(scholarship_api, accept)
            local_id = "local-" + draft_id
            assert accepted["routeId"] == local_id and not accepted["duplicate"] and accepted["draft"]["status"] == "ACCEPTED"
            local_data = request()
            assert {r["id"] for r in local_data["routes"]} == expected_routes | {local_id}
            local_route = next(r for r in local_data["routes"] if r["id"] == local_id)
            assert local_route["local"] and local_route["deadlineWindow2027"] == "UNKNOWN" and not local_route.get("applicationGuide")
            local_plan = next(o for o in local_data["overlays"] if o["routeId"] == local_id)
            assert not local_plan.get("tracked") and not local_plan.get("mainTarget") and "pursuitLevel" not in local_plan
            assert {e["id"] for e in local_data["calendarEvents"]} == expected_events
            assert not any(e["routeId"] == local_id for e in local_data["calendarEvents"])
            assert fields["scholarshipName"].encode() in request("/scholarships?browse=1")
            assert fields["scholarshipName"].encode() in request("/scholarships/" + local_id + "?tab=overview")
            repeated = request(scholarship_api, accept)
            assert repeated["routeId"] == local_id and repeated["draft"] == accepted["draft"]
            assert request()["state"] == local_data["state"]
            local_bundle = request("/api/schola/export")
            assert local_bundle["state"]["localScholarships"][local_id]["scholarshipName"] == fields["scholarshipName"]
            assert local_bundle["state"]["scholarshipDrafts"][draft_id] == accepted["draft"]
            request(value={"action": "brick", "key": "profile:sat-ticket", "done": False})
            request(value={"action": "import", "bundle": local_bundle})
            assert request()["state"] == local_bundle["state"]
            assert request(scholarship_api)["drafts"] == [accepted["draft"]]
            assert {r["id"] for r in request()["routes"]} == expected_routes | {local_id}
            # Imports must validate the local catalogue before replacing any
            # existing workspace state, including unrelated profile fields.
            preserved = request("/api/schola/export")
            for malicious_url in ("http://127.0.0.1/private", "https://university.edu/fixture?token=fictional-secret"):
                invalid = json.loads(json.dumps(preserved))
                invalid["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] = 99
                invalid["state"]["localScholarships"][local_id]["officialSourceUrl"] = malicious_url
                request(value={"action": "import", "bundle": invalid}, expect=400)
                current = request("/api/schola/export")
                assert all(current[key] == preserved[key] for key in ("revision", "profile", "overlays", "milestones", "state", "inbox"))
            assert request("/api/schola/chat")["messages"] == []
            scoped_chat = request("/api/schola/chat?routeId=" + quote(rid))
            assert scoped_chat["routeId"] == rid and scoped_chat["messages"] == []
            assert request("/api/schola/chat")["routeId"] is None
            request("/api/schola/chat?routeId=not-a-route", expect=400)
            request("/api/schola/chat?routeId=", expect=400)
            request("/api/schola/chat", {"action": "send", "routeId": [rid], "message": "Fixture", "id": "fixture-route-id"}, expect=400)
            request("/api/schola/chat", {"action": "send", "message": "Fixture"}, expect=400)
            password, salt = "fictional-http-password", "1234567890abcdef1234567890abcdef"
            access = {"enabled": True, "origins": [origin, "https://workspace.example:9443", "https://workspace.example:10000"], "sessionSecret": "fictional-session-secret-for-http-tests", "passwordSalt": salt, "passwordHash": hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024).hex()}
            (scratch / "private/schola.local.json").write_text(json.dumps({"access": access, "llm": {"baseUrl": "http://127.0.0.1:1/v1", "model": "fixture", "apiKey": "fictional-fixture-key"}, "search": {"provider": "disabled"}}))
            for route in ("/api/schola", "/api/schola/export", "/api/schola/chat", "/api/schola/chat?sessions=1", scholarship_api):
                request(route, expect=401)
            request(scholarship_api, {"action": "save", "id": draft_id, "revision": accepted["draft"]["revision"], "fields": fields}, expect=401)
            request("/api/session", {"password": "incorrect"}, expect=401)
            request("/api/session", {"password": password}, headers={"Origin": "https://attacker.invalid"}, expect=403)
            request("/api/session", {"password": password})
            cookie = last_headers["set-cookie"].split(";", 1)[0]
            assert "HttpOnly" in last_headers["set-cookie"] and "SameSite=strict" in last_headers["set-cookie"]
            # No worker runs here: queue scoping is checked without model traffic.
            chat_headers = {"Cookie": cookie}
            scoped_message = {"action": "send", "message": "Fictional scholarship question", "id": "fixture-scoped-chat", "routeId": rid}
            request("/api/schola/chat", scoped_message, headers=chat_headers, expect=202)
            request("/api/schola/chat", scoped_message, headers=chat_headers, expect=202)
            request("/api/schola/chat", {"action": "send", "message": "Fictional general question", "id": "fixture-general-chat"}, headers=chat_headers, expect=202)
            assert len(request("/api/schola/chat?routeId=" + quote(rid), headers=chat_headers)["messages"]) == 1
            assert [m["content"] for m in request("/api/schola/chat", headers=chat_headers)["messages"]] == ["Fictional general question"]
            assert request("/api/schola/chat?routeId=" + quote(data["routes"][1]["id"]), headers=chat_headers)["messages"] == []
            request("/api/schola/chat", {**scoped_message, "routeId": data["routes"][1]["id"]}, headers=chat_headers, expect=400)
            new_session = {"action": "start-session", "message": "Compare fictional deadlines", "id": "fixture-investigation"}
            request("/api/schola/chat", new_session, expect=401)
            opened = request("/api/schola/chat", new_session, headers=chat_headers, expect=202)
            session_id = opened["sessionId"]
            session_url = "/api/schola/chat?sessionId=" + quote(session_id)
            request(session_url, expect=401)
            steer = {"action": "steer-session", "sessionId": session_id, "message": "Use fictional intake B", "id": "fixture-investigation-steer"}
            request("/api/schola/chat", steer, headers={**chat_headers, "Origin": "https://attacker.invalid"}, expect=403)
            redirected = request("/api/schola/chat", steer, headers=chat_headers, expect=202)
            assert request("/api/schola/chat", steer, headers=chat_headers, expect=202)["jobId"] == redirected["jobId"]
            session = request(session_url, headers=chat_headers)
            assert [job["status"] for job in session["jobs"]] == ["QUEUED", "SUPERSEDED"]
            assert [m["content"] for m in session["messages"]] == [new_session["message"], steer["message"]]
            assert request("/api/schola/chat?sessions=1", headers=chat_headers)["sessions"][0]["id"] == session_id
            assert [m["content"] for m in request("/api/schola/chat", headers=chat_headers)["messages"]] == ["Fictional general question"]
            request(session_url + "&routeId=" + quote(rid), headers=chat_headers, expect=400)
            request("/api/schola/chat", {"action": "stop-session", "sessionId": session_id,
                                        "jobId": redirected["jobId"]}, headers=chat_headers, expect=202)
            assert request(session_url, headers=chat_headers)["session"]["status"] == "STOPPED"
            request("/schola?session=" + quote(session_id), headers=chat_headers)
            for route in ("/api/schola", "/api/schola/export", "/api/schola/chat", scholarship_api, "/schola"):
                request(route, headers={"Cookie": cookie})
            request(headers={"Cookie": "studab27-session=forged"}, expect=401)
            for host in ("workspace.example.attacker.invalid:10000", "workspace.example:9000", "workspace.example"):
                request(headers={"Host": host, "Cookie": cookie}, expect=403)
            for suffix in (9443, 10000):
                public = f"https://workspace.example:{suffix}"
                request("/api/session", {"password": password}, headers={"Host": f"workspace.example:{suffix}", "Origin": public})
                assert "Secure" in last_headers["set-cookie"]
                request(headers={"Host": f"workspace.example:{suffix}", "Cookie": cookie})
                request(value={"action": "simulate", "sat": 1500, "cap": 6}, headers={"Host": f"workspace.example:{suffix}", "Origin": public, "Cookie": cookie})
                request(value={"action": "simulate", "sat": 1500, "cap": 6}, headers={"Host": f"workspace.example:{suffix}", "Origin": public.replace("https:", "http:"), "Cookie": cookie}, expect=403)
            request("/api/session", {"action": "logout"}, headers={"Cookie": cookie})
            assert "Max-Age=0" in last_headers["set-cookie"]
            lan_origin, lan_password, lan_proxy = "http://192.168.0.100:3270", "fictional-lan-password", "fictional-lan-proxy-secret"
            access["lan"] = {"origin": lan_origin, "proxySecret": lan_proxy, "passwordSalt": salt,
                             "passwordHash": hashlib.scrypt(lan_password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024).hex(),
                             "sessionSecret": "fictional-lan-session-secret"}
            (scratch / "private/schola.local.json").write_text(json.dumps({"access": access}))
            lan_headers = {"Host": "192.168.0.100:3270", "Origin": lan_origin, "x-studab-lan-proxy": lan_proxy}
            request(headers={"Host": "192.168.0.100:3270"}, expect=403)
            request("/api/session", {"password": lan_password}, headers={"Origin": "https://workspace.example:10000", "Host": "workspace.example:10000"}, expect=401)
            request("/api/session", {"password": password}, headers=lan_headers, expect=401)
            request("/api/session", {"password": lan_password}, headers=lan_headers)
            lan_cookie = last_headers["set-cookie"].split(";", 1)[0]
            assert "Secure" not in last_headers["set-cookie"]
            request(headers={**lan_headers, "Cookie": lan_cookie})
            request(headers={"Host": "workspace.example:10000", "Cookie": lan_cookie}, expect=401)
            request(headers={**lan_headers, "Cookie": cookie}, expect=401)
            request(value={"action": "simulate", "sat": 1500, "cap": 6}, headers={**lan_headers, "Cookie": lan_cookie, "Origin": "http://attacker.invalid"}, expect=403)
            print(f"Production HTTP: tracker, documents, {len(expected_routes)} public scholarship pages, scoped dashboard and calendar prerequisites, reviewed local additions, draft conflicts, checklist persistence, calendar reads, export/import recovery, signed sessions, exact origins and CSRF guards passed.")
        finally:
            server.terminate()
            try: server.wait(timeout=8)
            except subprocess.TimeoutExpired: server.kill(); server.wait()
            log.close()


if __name__ == "__main__":
    main()
