"""Production HTTP smoke check in a temporary fictional workspace.

Exercises persistence and recovery without touching the owner's vault.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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
            return json.loads(content) if "application/json" in response_headers.get("Content-Type", "") else content

        log = (scratch / "server.log").open("w")
        server = subprocess.Popen(["node", str(root / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(port)], cwd=scratch, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "STUDAB27_DEMO": "0"})
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
            for route in ("/", "/catalogue", "/bricks", "/watchtower"): request(route)
            request(value={"action": "task", "id": "sat-registration", "command": "done"})
            assert request()["state"]["tasks"]["sat-registration"]["status"] == "DONE"
            request(value={"action": "task", "id": "sat-registration", "command": "undo"})
            request(value={"action": "brick", "key": "profile:sat-ticket", "done": True})
            assert request()["state"]["bricks"]["profile:sat-ticket"]
            rid = data["routes"][0]["id"]
            request(value={"action": "overlay", "id": rid, "patch": {"applicationStatus": "RESEARCHING", "notes": "Fictional persistence check"}})
            assert request()["overlays"][0]["applicationStatus"] == "RESEARCHING"
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
            assert list((scratch / "private/backups").glob("*.local.json"))
            bad = {**bundle, "overlays": bundle["overlays"][:-1]}
            request(value={"action": "import", "bundle": bad}, expect=400)
            assert request()["profile"]["snapshot"]["maxFamilyContributionIdrMPerMonth"] == 6
            print("Production HTTP: demo fallback, four pages, persisted task/document/route/inbox actions, scenario isolation, origin/host guards, export, validated import and recovery backup passed.")
        finally:
            server.terminate()
            try: server.wait(timeout=8)
            except subprocess.TimeoutExpired: server.kill(); server.wait()
            log.close()


if __name__ == "__main__":
    main()
