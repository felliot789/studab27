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
import http.client
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import threading
import time
from urllib.parse import urljoin, urlsplit
from datetime import datetime, timezone

from .research_sources import MAX_CANDIDATE_LINKS, prioritize_source_links, source_link

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
    return parts, addresses[0][4][0]


class PinnedHTTP(http.client.HTTPConnection):
    """Connect to the validated IP without a second DNS lookup or proxy env."""
    def __init__(self, host, port, address, secure=False):
        super().__init__(host, port=port, timeout=14)
        self.address, self.secure = address, secure

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        if self.secure:
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)


class TextParser(HTMLParser):
    def __init__(self, base_url=""):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.text = []
        self.pdfs = []
        self.links = []
        self.base_url = base_url
        self.form_depth = 0
        self.anchor = None

    def finish_anchor(self):
        if self.anchor and len(self.links) < MAX_CANDIDATE_LINKS:
            link = source_link(self.anchor[0], "".join(self.anchor[1]), self.base_url)
            if link and all(existing["url"] != link["url"] for existing in self.links):
                self.links.append(link)
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "form":
            self.form_depth += 1
        if tag == "a":
            self.finish_anchor()
            attributes = dict(attrs)
            href = attributes.get("href") or ""
            if re.search(r"\.pdf(?:[?#]|$)", href, re.I):
                self.pdfs.append(href)
            if not self.skip and not self.form_depth and "download" not in attributes and "hidden" not in attributes and attributes.get("aria-hidden") != "true":
                self.anchor = (href, [])

    def handle_endtag(self, tag):
        if tag == "a":
            self.finish_anchor()
        if tag == "form" and self.form_depth:
            self.form_depth -= 1
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "br"):
            self.text.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
            if self.anchor:
                self.anchor[1].append(data)


def normalize(data, content_type, url):
    result = normalize_source(data, content_type, url)
    return result["text"], result["pdfLinks"]


def normalize_source(data, content_type, url):
    """Normalize one response and discover links without fetching their targets."""
    source_links = []
    if data.startswith(b"%PDF") or "application/pdf" in content_type:
        if not shutil.which("pdftotext"):
            raise ValueError("PDF text unavailable: install Poppler pdftotext; no baseline updated")
        value = subprocess.run(["pdftotext", "-layout", "-", "-"], input=data, capture_output=True, timeout=30, check=True).stdout.decode("utf-8")
        links = []
    elif "html" in content_type or data.lstrip().startswith(b"<"):
        match = re.search(r"charset=([\w-]+)", content_type, re.I)
        parser = TextParser(url)
        parser.feed(data.decode(match[1] if match else "utf-8", errors="replace"))
        parser.close()
        parser.finish_anchor()
        value = "".join(parser.text)
        links = sorted(set(urljoin(url, link) for link in parser.pdfs))
        source_links = prioritize_source_links(parser.links)
    else:
        raise ValueError("Unsupported source type; HTML or text-readable PDF required")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    text = "\n".join(line for line in lines if line)
    if len(text) < 100 or re.search(r"^(?:just a moment|access denied|attention required|verify you are human)", text, re.I):
        raise ValueError("Empty, blocked, or challenge page; previous baseline preserved")
    return {"text": text, "pdfLinks": links, "links": source_links, "finalUrl": url}


def fetch(url):
    validate_public_url(url)
    host = urlsplit(url).hostname
    with HOST_LOCKS_GUARD:
        lock = HOST_LOCKS.setdefault(host, threading.Lock())
    with lock:
        try:
            current = url
            for redirect in range(6):
                parts, address = validate_public_url(current)
                connection = PinnedHTTP(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), address, secure=parts.scheme == "https")
                try:
                    connection.request("GET", (parts.path or "/") + ("?" + parts.query if parts.query else ""), headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf"})
                    response = connection.getresponse()
                    if response.status in (301, 302, 303, 307, 308):
                        if not response.getheader("Location"):
                            raise ValueError("Source redirected without a destination")
                        current = urljoin(current, response.getheader("Location"))
                        continue  # The next connection validates and pins its own IP.
                    if response.status != 200:
                        raise ValueError(f"Source returned HTTP {response.status}")
                    if int(response.getheader("Content-Length", "0")) > MAX_BYTES:
                        raise ValueError("Source exceeds size limit")
                    chunks, total, started = [], 0, time.monotonic()
                    while True:
                        if time.monotonic() - started > 45:
                            raise ValueError("Source exceeded read deadline")
                        chunk = response.read1(min(128 * 1024, MAX_BYTES + 1 - total))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError("Source exceeds size limit")
                    data = b"".join(chunks)
                    return normalize_source(data, response.getheader("Content-Type", ""), current)
                finally:
                    connection.close()
            raise ValueError("Source exceeded redirect limit")
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
