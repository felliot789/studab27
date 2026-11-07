"""Bounded, non-fetching helpers for navigating untrusted source content."""

import ipaddress
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_SOURCE_LINKS = 60
MAX_CANDIDATE_LINKS = 240
MAX_EXCERPT_CHARS = 16000
_RESEARCH_LINK_TERMS = re.compile(r"scholarship|admission|apply|application|deadline|eligibility|undergraduate|funding|\.pdf", re.I)
_UNREADABLE_SUFFIXES = re.compile(
    r"\.(?:zip|rar|7z|gz|exe|msi|dmg|apk|jpg|jpeg|png|gif|svg|webp|ico|mp3|mp4|avi|woff2?|ttf|css|js)$", re.I
)


def source_link(href, label, base_url):
    """Return a candidate link; actual fetches must still validate DNS and IPs."""
    if not isinstance(href, str) or not href.strip() or href.lstrip().startswith("#"):
        return None
    if len(href) > 2048 or any(ord(char) < 32 or ord(char) == 127 for char in href):
        return None
    try:
        parts = urlsplit(urljoin(base_url, href.strip()))
        host = (parts.hostname or "").lower().rstrip(".")
        if (parts.scheme not in ("http", "https") or not host or parts.username or parts.password
                or parts.port not in (None, 80, 443) or host == "localhost"
                or host.endswith((".localhost", ".local", ".internal"))):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
        if _UNREADABLE_SUFFIXES.search(parts.path):
            return None
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        if len(url) > 2048 or url == base_url.split("#", 1)[0]:
            return None
    except ValueError:
        return None
    text = (re.sub(r"\s+", " ", label).strip() or url)[:240]
    return {"url": url, "text": text}


def prioritize_source_links(links):
    """Prefer research links over generic navigation, retaining order for ties."""
    return sorted(links, key=lambda link: -len(set(_RESEARCH_LINK_TERMS.findall(
        (link["text"] + " " + urlsplit(link["url"]).path).lower()
    ))))[:MAX_SOURCE_LINKS]


def read_source_excerpt(text, *, offset=0, limit=12000, query=""):
    """Page through normalized text, or center a literal query match with context."""
    limit = max(1, min(MAX_EXCERPT_CHARS, int(limit)))
    offset = max(0, min(len(text), int(offset)))
    query = query.strip()[:240]
    match = re.search(re.escape(query), text, re.I) if query else None
    if match:
        offset = max(0, match.start() - limit // 4)
    end = min(len(text), offset + limit)
    return {
        "text": text[offset:end], "offset": offset, "nextOffset": end if end < len(text) else None,
        "totalChars": len(text), "truncated": offset > 0 or end < len(text), "matchedQuery": bool(match),
    }
