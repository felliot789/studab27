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
import tempfile
import time
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

        log = (scratch / "server.log").open("w")
        server = subprocess.Popen(["node", str(root / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(port)], cwd=scratch, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "STUDAB27_DEMO": "0", "STUDAB27_CONFIG_PATH": str(scratch / "private/schola.local.json")})
        try:
            for attempt in range(80):
                if server.poll() is not None: raise AssertionError("Temporary app server exited")
                try:
                    with urlopen(origin, timeout=1) as response:
                        if response.status == 200: break
                except (OSError, TimeoutError): time.sleep(.15)
            else: raise AssertionError("Temporary app server did not become ready")
            data = request()
            assert data["mode"] == "DEMO" and len(data["routes"]) == 57 and len(data["briefing"]["cards"]) == 3
            assert len(data["calendarEvents"]) == 174
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
            scenario = request(value={"action": "simulate", "sat": 1560, "cap": 8})
            assert len(scenario["evaluations"]) == 57
            assert request()["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] == 5
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
            bad_progress["state"]["requirements"][guide_id][step["id"]]["status"] = "NOT_NEEDED"
            request(value={"action": "import", "bundle": bad_progress}, expect=400)
            assert request()["state"]["requirements"] == progress
            assert list((scratch / "private/backups").glob("*.local.json"))
            bad = {**bundle, "overlays": bundle["overlays"][:-1]}
            request(value={"action": "import", "bundle": bad}, expect=400)
            assert request()["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] == 6
            assert request("/api/schola/chat")["messages"] == []
            request("/api/schola/chat", {"action": "send", "message": "Fixture"}, expect=400)
            password, salt = "fictional-http-password", "1234567890abcdef1234567890abcdef"
            access = {"enabled": True, "origins": [origin, "https://workspace.example:9443", "https://workspace.example:10000"], "sessionSecret": "fictional-session-secret-for-http-tests", "passwordSalt": salt, "passwordHash": hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024).hex()}
            (scratch / "private/schola.local.json").write_text(json.dumps({"access": access, "llm": {}, "search": {"provider": "disabled"}}))
            for route in ("/api/schola", "/api/schola/export", "/api/schola/chat"):
                request(route, expect=401)
            request("/api/session", {"password": "incorrect"}, expect=401)
            request("/api/session", {"password": password}, headers={"Origin": "https://attacker.invalid"}, expect=403)
            request("/api/session", {"password": password})
            cookie = last_headers["set-cookie"].split(";", 1)[0]
            assert "HttpOnly" in last_headers["set-cookie"] and "SameSite=strict" in last_headers["set-cookie"]
            for route in ("/api/schola", "/api/schola/export", "/api/schola/chat", "/schola"):
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
            print("Production HTTP: tracker, documents, 57 scholarship pages, priority changes, checklist persistence, safe removal, calendar reads, export/import recovery, signed sessions, exact origins and CSRF guards passed.")
        finally:
            server.terminate()
            try: server.wait(timeout=8)
            except subprocess.TimeoutExpired: server.kill(); server.wait()
            log.close()


if __name__ == "__main__":
    main()
