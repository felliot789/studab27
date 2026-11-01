"""Bounded official-source monitor. First fetch is a baseline, never a change.

Default output is the ignored local vault. --public emits public-only observations
for CI; private files are never read by this module.
"""
import argparse
import concurrent.futures
import contextlib
import difflib
import fcntl
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 12 * 1024 * 1024
USER_AGENT = "StudAb27-Schola/0.1 (personal scholarship source monitor; 12-hour cadence)"
HOST_LOCKS = {}
HOST_LOCKS_GUARD = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(".tmp")
    with temp.open("w") as f:
        temp.chmod(0o600)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    temp.replace(path)


def validate_public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.port not in (None, 80, 443):
        raise ValueError("Only public HTTP(S) source URLs are allowed")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Source resolves to a nonpublic address")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.text = []
        self.pdfs = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href", "")
            if re.search(r"\.pdf(?:[?#]|$)", href, re.I):
                self.pdfs.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "br"):
            self.text.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def normalize(data, content_type, url):
    if data.startswith(b"%PDF") or "application/pdf" in content_type:
        if not shutil.which("pdftotext"):
            raise ValueError("PDF text unavailable: install Poppler pdftotext; no baseline updated")
        value = subprocess.run(["pdftotext", "-layout", "-", "-"], input=data, capture_output=True, timeout=30, check=True).stdout.decode("utf-8")
        links = []
    elif "html" in content_type or data.lstrip().startswith(b"<"):
        match = re.search(r"charset=([\w-]+)", content_type, re.I)
        parser = TextParser()
        parser.feed(data.decode(match[1] if match else "utf-8", errors="replace"))
        value = "".join(parser.text)
        links = sorted(set(urljoin(url, link) for link in parser.pdfs))
    else:
        raise ValueError("Unsupported source type; HTML or text-readable PDF required")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    text = "\n".join(line for line in lines if line)
    if len(text) < 100 or re.search(r"^(?:just a moment|access denied|attention required|verify you are human)", text, re.I):
        raise ValueError("Empty, blocked, or challenge page; previous baseline preserved")
    return text, links


def fetch(url):
    validate_public_url(url)
    host = urlsplit(url).hostname
    with HOST_LOCKS_GUARD:
        lock = HOST_LOCKS.setdefault(host, threading.Lock())
    with lock:
        try:
            opener = build_opener(SafeRedirect())
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf"})
            with opener.open(req, timeout=14) as response:
                if int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
                    raise ValueError("Source exceeds size limit")
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("Source exceeds size limit")
                text, links = normalize(data, response.headers.get("Content-Type", ""), response.url)
                return {"text": text, "pdfLinks": links, "finalUrl": response.url}
        finally:
            time.sleep(0.6)


def record_success(url, result, previous, snapshots, route_ids):
    text = result["text"]
    digest = hashlib.sha256(text.encode()).hexdigest()
    key = hashlib.sha256(url.encode()).hexdigest()
    path = snapshots / f"{key}.txt"
    old = path.read_text() if path.exists() else ""
    timestamp = now()
    event = None
    if not previous.get("hash"):
        event = {"kind": "BASELINE", "summary": "First successful snapshot; no change inferred.", "excerpt": ""}
    elif previous["hash"] != digest:
        changes = [line[:350] for line in difflib.unified_diff(old.splitlines(), text.splitlines(), n=1) if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
        event = {"kind": "CHANGED", "summary": "Official-source text changed. Review before updating any rule or deadline.", "excerpt": "\n".join(changes[:12]) if old else "Text changed; prior local text snapshot is unavailable."}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text)
    temporary.chmod(0o600)
    temporary.replace(path)
    record = {"status": "OK", "hash": digest, "lastCheckedAt": timestamp, "lastSuccessAt": timestamp, "routeIds": route_ids, "pdfLinks": result["pdfLinks"], "finalUrl": result["finalUrl"]}
    if event:
        event.update({"url": url, "routeIds": route_ids, "at": timestamp, "id": hashlib.sha256(f"{url}{digest}{timestamp}".encode()).hexdigest()[:20]})
    return record, event


def scan(root=ROOT, public=False, limit=None):
    vault = root / "private"
    vault.mkdir(exist_ok=True, mode=0o700)
    lock_path = vault / "watchtower.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("A Schola scan is already running")
        path = root / "data/public/watchtower_state.json" if public else vault / "watchtower_state.local.json"
        state = json.loads(path.read_text()) if path.exists() else {"sources": {}, "events": []}
        state["runStartedAt"] = now()
        state["running"] = True
        state["runComplete"] = False
        state["progress"] = {"checked": 0, "total": 0}
        atomic_json(path, state)
        routes = json.loads((root / "data/public/scholarships_2027.json").read_text())
        sources = {}
        for r in routes:
            for url in (r.get("officialSourceUrl"), r.get("secondarySourceUrl")):
                if url:
                    sources.setdefault(url, []).append(r["id"])
        notes_path = root / "data/public/source_verifications.json"
        if notes_path.exists():
            for note in json.loads(notes_path.read_text()):
                for url in (note.get("sourceUrl"), note.get("secondaryUrl")):
                    if url:
                        sources.setdefault(url, [])
                        if note.get("routeId") and note["routeId"] not in sources[url]:
                            sources[url].append(note["routeId"])
        if limit:
            sources = dict(list(sources.items())[:limit])
        state["progress"]["total"] = len(sources)
        atomic_json(path, state)
        events = []
        snapshots = vault / "watchtower/snapshots"

        def batch(urls):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                jobs = {pool.submit(fetch, url): url for url in urls}
                for future in concurrent.futures.as_completed(jobs):
                    url = jobs[future]
                    old = state["sources"].get(url, {})
                    try:
                        result = future.result()
                        record, event = record_success(url, result, old, snapshots, sources[url])
                        state["sources"][url] = record
                        if event:
                            events.append(event)
                    except Exception as exc:
                        # No response body or private file data in public error output.
                        state["sources"][url] = {**old, "status": "ERROR", "lastCheckedAt": now(), "routeIds": sources[url], "error": f"{type(exc).__name__}: {str(exc)[:220]}"}
                        if old.get("status") != "ERROR":
                            timestamp = now()
                            events.append({"id": hashlib.sha256(f"{url}{timestamp}".encode()).hexdigest()[:20], "kind": "ERROR", "at": timestamp, "url": url, "routeIds": sources[url], "summary": "Fetch failed; last good baseline retained.", "excerpt": ""})
                    state["progress"] = {"checked": sum(1 for v in state["sources"].values() if v.get("lastCheckedAt", "") >= state["runStartedAt"]), "total": len(sources)}
                    state["events"] = (events + state.get("events", []))[:300]
                    events.clear()
                    atomic_json(path, state)

        batch(list(sources))
        pdfs = {}
        for url in list(sources):
            record = state["sources"].get(url, {})
            for link in record.get("pdfLinks", [])[:2]:
                if urlsplit(link).hostname == urlsplit(record.get("finalUrl", url)).hostname and link not in sources:
                    pdfs.setdefault(link, []).extend(sources[url])
        sources.update({k: list(set(v)) for k, v in pdfs.items()})
        if pdfs:
            batch(list(pdfs))
        state.update({"running": False, "runComplete": True, "lastRunAt": now(), "scope": "LIMITED" if limit else "CATALOGUE_AND_LINKED_PDFS", "summary": {"checked": len(sources), "ok": sum(state["sources"][u]["status"] == "OK" for u in sources), "errors": sum(state["sources"][u]["status"] == "ERROR" for u in sources)}})
        atomic_json(path, state)
        print(json.dumps(state["summary"]))
        return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    scan(public=args.public, limit=args.limit)
