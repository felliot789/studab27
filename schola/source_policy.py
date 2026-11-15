"""Exact candidate admission; source readability never establishes authority.

Only callers holding a user-supplied URL, a search result or an actually fetched
link may admit it. The fetcher still validates and pins public DNS/IPs, including
every redirect. These helpers do not fetch, trust a TLD or promote sibling URLs.
"""

import ipaddress
import re
from urllib.parse import parse_qsl, urlsplit

from .research_sources import source_link

_SECRET_PARAMETER = re.compile(
    r"^(?:.*token|.*secret|.*password|api[-_]?key|authorization|auth|credential[s]?|"
    r"session(?:id)?|signature|key|access[-_]?key|x-amz-.*|x-goog-.*)$", re.I
)


def candidate_source_url(url):
    """Return a syntactically public source candidate, without DNS or I/O."""
    if (not isinstance(url, str) or not url.startswith(("https://", "http://"))
            or len(url) > 2048 or any(char.isspace() or char == "\\" for char in url)):
        return None
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        if (parts.username is not None or parts.password is not None
                or host.endswith((".invalid", ".test", ".example", ".onion", ".lan", ".home"))):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            ascii_host = host.encode("idna").decode("ascii")
            if ("." not in ascii_host or re.fullmatch(r"[0-9.]+", ascii_host)
                    or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                           for label in ascii_host.split("."))):
                return None
        else:
            if not address.is_global or address.is_multicast:
                return None
        if any(host == domain or host.endswith("." + domain)
               for domain in ("drive.google.com", "calendar.google.com", "docs.google.com")):
            return None
        if host in ("google.com", "www.google.com") and parts.path.casefold().startswith("/calendar"):
            return None
        if any(_SECRET_PARAMETER.fullmatch(key) for key, _ in parse_qsl(
                parts.query + "&" + parts.fragment, keep_blank_values=True)):
            return None
        link = source_link(url, "", "")
    except (ValueError, UnicodeError):
        return None
    return link["url"] if link is not None else None


def admit_candidate_urls(readable_urls, urls):
    """Admit exact evidenced candidates only; no invented paths or parameters."""
    admitted = []
    for url in urls:
        candidate = candidate_source_url(url)
        if candidate is None:
            continue
        key = candidate.split("#", 1)[0].rstrip("/")
        readable_urls.add(key)
        if key not in admitted:
            admitted.append(key)
    return admitted
