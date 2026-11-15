"""Reviewable scholarship drafts and owner-accepted local catalogue records.

These live in workspace state, so ordinary transactional saves, export and
recovery include them. Models may propose drafts; only the owner-facing accept
action calls accept_draft. URL checks here do not fetch or resolve DNS: actual
source reads must additionally use the watcher's pinned-address protection.
"""
from datetime import date, datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import parse_qsl, urlsplit, urlunsplit
import uuid


TEXT_FIELDS = (
    "country", "institution", "scholarshipName", "programAndLanguageNotes",
    "benefitsCoverage", "indonesianApplicantNotes", "languageOrTestNotes",
    "separateScholarshipApp", "preGradApplyAllowed", "renewalAndBondTerms",
    "publicRiskOrCaveat", "officialSourceUrl",
)
FIELD_KEYS = set(TEXT_FIELDS) | {"unresolvedQuestions"}
IDENTITY_FIELDS = ("country", "institution", "scholarshipName")
ROUTE_STRINGS = (
    "id", "country", "institution", "scholarshipName", "fundingType",
    "engineeringFit", "benefitsCoverage", "satRole", "suggestedSatBenchmark",
    "languageOrTestNotes", "deadlineWindow2027", "preGradApplyAllowed",
    "separateScholarshipApp", "renewalAndBondTerms", "publicRiskOrCaveat",
    "officialSourceUrl", "secondarySourceUrl", "seedStatus",
)
ROUTE_OPTIONAL_STRINGS = (
    "currentCycleStatus", "currentCycleEvidenceSummary", "reviewedAt",
    "indonesianApplicantNotes", "programAndLanguageNotes", "aiContentPolicy",
)
ROUTE_KEYS = set(ROUTE_STRINGS + ROUTE_OPTIONAL_STRINGS) | {
    "local", "unresolvedQuestions", "evidenceSources", "fieldReview",
}
DRAFT_KEYS = {
    "id", "revision", "status", "query", "jobId", "createdAt", "updatedAt",
    "fields", "sources", "matches", "acceptedRouteId", "error",
    "leadSourceUrl",
}
STATUSES = {"RESEARCHING", "READY", "FAILED", "ACCEPTED"}
MAX_RECORDS = 500
MAX_SOURCES = 60
_UNSAFE_KEYS = {"__proto__", "prototype", "constructor"}
_SECRET_PARAMETER = re.compile(
    r"^(?:.*token|.*secret|.*password|api[-_]?key|authorization|auth|credential[s]?|"
    r"session(?:id)?|signature|key|access[-_]?key|x-amz-.*|x-goog-.*)$", re.I
)


def _text(value, maximum=4000, *, nonempty=False):
    if (not isinstance(value, str) or len(value) > maximum
            or any(ord(char) < 32 and char not in "\n\t\r" for char in value)):
        raise ValueError(f"Text must contain at most {maximum} characters.")
    value = value.strip()
    if nonempty and not value:
        raise ValueError("A nonempty value is required.")
    return value


def _safe_keys(value, depth=0):
    if depth > 20:
        raise ValueError("Catalogue data is nested too deeply.")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or key in _UNSAFE_KEYS:
                raise ValueError("Unsupported catalogue object key.")
            _safe_keys(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _safe_keys(child, depth + 1)


def _object(value, allowed):
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Unsupported catalogue fields.")
    _safe_keys(value)
    return value


def public_source_url(value):
    """Validate a public-looking HTTP(S) URL without performing DNS or I/O."""
    from .source_policy import candidate_source_url
    value = _text(value, 2048, nonempty=True)
    if any(char.isspace() or char == "\\" for char in value) or candidate_source_url(value) is None:
        raise ValueError("Use a public HTTP(S) source URL.")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower().rstrip(".")
        if (parts.scheme not in ("http", "https") or not host
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 80, 443)
                or host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".onion"))):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            ascii_host = host.encode("idna").decode("ascii")
            if ("." not in ascii_host or re.fullmatch(r"[0-9.]+", ascii_host)
                    or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                           for label in ascii_host.split("."))):
                raise ValueError()
        else:
            if not address.is_global or address.is_multicast:
                raise ValueError()
        if any(host == domain or host.endswith("." + domain)
               for domain in ("drive.google.com", "calendar.google.com", "docs.google.com")):
            raise ValueError()
        if host in ("google.com", "www.google.com") and parts.path.startswith("/calendar"):
            raise ValueError()
        if any(_SECRET_PARAMETER.fullmatch(key) for key, _ in parse_qsl(parts.query + "&" + parts.fragment)):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise ValueError("Use a public HTTP(S) source URL without private links or credentials.") from None
    return value


def _url_key(value):
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def _identifier(value):
    original = value
    value = _text(value, 36, nonempty=True)
    if value != original:
        raise ValueError("A canonical UUID draft identifier is required.")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise ValueError("A UUID draft identifier is required.") from None
    if value not in (str(parsed), parsed.hex):
        raise ValueError("A canonical UUID draft identifier is required.")
    return value


def _revision(value):
    if type(value) is not int or value < 1:
        raise ValueError("A draft revision is required.")
    return value


def _timestamp(value, *, lifecycle=False):
    original = value
    value = _text(value, 64, nonempty=True)
    if lifecycle and value != original:
        raise ValueError("Use a canonical timestamp with a timezone.")
    try:
        if len(value) == 10:
            if lifecycle:
                raise ValueError()
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
        elif datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError("Use an ISO date or timestamp with a timezone.") from None
    return value


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate_fields(value, *, require_identity=False):
    value = _object(value, FIELD_KEYS)
    fields = {}
    for name in TEXT_FIELDS:
        maximum = 100 if name == "country" else 300 if name in ("institution", "scholarshipName") else 2048 if name == "officialSourceUrl" else 4000
        fields[name] = _text(value.get(name, "" if name == "officialSourceUrl" else "UNKNOWN"), maximum) or ("" if name == "officialSourceUrl" else "UNKNOWN")
    if fields["officialSourceUrl"]:
        fields["officialSourceUrl"] = public_source_url(fields["officialSourceUrl"])
    questions = value.get("unresolvedQuestions", [])
    if not isinstance(questions, list) or len(questions) > 30:
        raise ValueError("At most 30 unresolved questions are supported.")
    fields["unresolvedQuestions"] = [_text(question, 1000, nonempty=True) for question in questions]
    if require_identity:
        if any(fields[key].upper() == "UNKNOWN" for key in IDENTITY_FIELDS) or not fields["officialSourceUrl"]:
            raise ValueError("Country, institution, scholarship name and an official source URL are required before adding a scholarship.")
    return fields


def _sources(value, *, evidence=False):
    if not isinstance(value, list) or len(value) > MAX_SOURCES:
        raise ValueError(f"At most {MAX_SOURCES} source records are supported.")
    result = []
    allowed = {"url", "checkedAt", "finding"} if evidence else {"url", "title", "finding", "checkedAt"}
    for raw in value:
        source = _object(raw, allowed)
        item = {"url": public_source_url(source.get("url")), "checkedAt": _timestamp(source.get("checkedAt"))}
        for key, maximum in (("title", 500), ("finding", 6000)):
            if key in source:
                item[key] = _text(source[key], maximum)
        result.append(item)
    return result


def _normalized(value):
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def _matches(fields, routes, *, exclude=None):
    institution = _normalized(fields["institution"])
    name = _normalized(fields["scholarshipName"])
    source = fields.get("officialSourceUrl")
    matches = []
    for route in routes:
        other = _normalized(route["institution"])
        same_institution = institution not in ("", "unknown") and institution == other
        related_name = (len(institution) >= 5 and len(other) >= 5 and
                        (institution.startswith(other + " ") or other.startswith(institution + " ")))
        same_source = bool(source and route.get("officialSourceUrl") and _url_key(source) == _url_key(route["officialSourceUrl"]))
        if route["id"] != exclude and (same_institution or related_name or same_source):
            matches.append({"routeId": route["id"], "institution": route["institution"],
                            "scholarshipName": route["scholarshipName"],
                            "kind": "EXACT" if same_institution and name != "unknown" and name == _normalized(route["scholarshipName"]) else "POSSIBLE"})
    return matches


def _public_routes(root):
    path = Path(root) / "data/public/scholarships_2027.json"
    return json.loads(path.read_text()) if path.exists() else []


def all_routes(root, workspace=None):
    from . import workspace_store
    workspace = workspace if workspace is not None else workspace_store.load(root)
    public = _public_routes(root)
    validate_catalogue_state(workspace["state"], public)
    return public + list(workspace["state"].get("localScholarships", {}).values())


def validate_catalogue_state(state, public_routes=None):
    """Validate imported optional records; never change the caller's state."""
    if not isinstance(state, dict):
        raise ValueError("Workspace state must be an object.")
    drafts = state.get("scholarshipDrafts", {})
    routes = state.get("localScholarships", {})
    if not isinstance(drafts, dict) or not isinstance(routes, dict) or len(drafts) > MAX_RECORDS or len(routes) > MAX_RECORDS:
        raise ValueError(f"Local catalogue supports at most {MAX_RECORDS} drafts and scholarships.")
    _safe_keys(drafts)
    _safe_keys(routes)
    public_ids = {route["id"] for route in public_routes or []}
    for route_id, route in routes.items():
        _object(route, ROUTE_KEYS)
        if not route_id.startswith("local-") or route_id in public_ids or route.get("id") != route_id or route.get("local") is not True:
            raise ValueError("Local scholarships require separate permanent identifiers.")
        _identifier(route_id.removeprefix("local-"))
        for key in ROUTE_STRINGS:
            _text(route.get(key), 2048 if key in ("officialSourceUrl", "secondarySourceUrl") else 4000, nonempty=key != "secondarySourceUrl")
        for key in ROUTE_OPTIONAL_STRINGS:
            if key in route:
                _text(route[key], 4000)
        validate_fields({key: route[key] for key in FIELD_KEYS if key in route}, require_identity=True)
        if route["secondarySourceUrl"]:
            public_source_url(route["secondarySourceUrl"])
        if "reviewedAt" in route:
            _timestamp(route["reviewedAt"])
        _sources(route.get("evidenceSources", []), evidence=True)
        reviews = route.get("fieldReview", {})
        if not isinstance(reviews, dict) or set(reviews) - (set(ROUTE_STRINGS + ROUTE_OPTIONAL_STRINGS) - {"id"}):
            raise ValueError("Invalid local scholarship field reviews.")
        for review in reviews.values():
            _object(review, {"status", "evidence"})
            if review.get("status") != "DRAFT_NOT_ELIGIBILITY_VERIFICATION" or review.get("evidence") != []:
                raise ValueError("Local draft field reviews cannot claim verified evidence.")
    retained_ids = public_ids | set(routes)
    for draft_id, draft in drafts.items():
        _identifier(draft_id)
        _object(draft, DRAFT_KEYS)
        if draft.get("id") != draft_id or not isinstance(draft.get("status"), str) or draft["status"] not in STATUSES:
            raise ValueError("Invalid scholarship draft identity or status.")
        _revision(draft.get("revision"))
        _text(draft.get("query"), 1000, nonempty=True)
        if "leadSourceUrl" in draft:
            lead_source = _text(draft["leadSourceUrl"], 2048)
            if lead_source:
                public_source_url(lead_source)
        _text(draft.get("jobId"), 150, nonempty=True)
        _timestamp(draft.get("createdAt"), lifecycle=True)
        _timestamp(draft.get("updatedAt"), lifecycle=True)
        validate_fields(draft.get("fields"), require_identity=draft["status"] == "ACCEPTED")
        _sources(draft.get("sources"))
        matches = draft.get("matches")
        if not isinstance(matches, list) or len(matches) > MAX_RECORDS:
            raise ValueError("Invalid scholarship duplicate matches.")
        for match in matches:
            _object(match, {"routeId", "institution", "scholarshipName", "kind"})
            _text(match.get("routeId"), 150, nonempty=True)
            _text(match.get("institution"), 300, nonempty=True)
            _text(match.get("scholarshipName"), 300, nonempty=True)
            if match.get("kind") not in ("EXACT", "POSSIBLE"):
                raise ValueError("Invalid scholarship duplicate match kind.")
        if "error" in draft:
            _text(draft["error"], 1000)
        if draft["status"] == "ACCEPTED":
            if draft.get("acceptedRouteId") != "local-" + draft_id or draft["acceptedRouteId"] not in retained_ids:
                raise ValueError("Accepted drafts must retain their local scholarship.")
            if any(draft["fields"][key] != routes[draft["acceptedRouteId"]][key] for key in IDENTITY_FIELDS):
                raise ValueError("Accepted draft identity must match its local scholarship.")
        elif "acceptedRouteId" in draft:
            raise ValueError("Only accepted drafts may identify an accepted scholarship.")


def list_drafts(root):
    from . import workspace_store
    workspace = workspace_store.load(root)
    validate_catalogue_state(workspace["state"], _public_routes(root))
    return sorted(workspace["state"].get("scholarshipDrafts", {}).values(), key=lambda draft: draft["updatedAt"], reverse=True)


def get_draft(root, draft_id):
    draft_id = _identifier(draft_id)
    return next((draft for draft in list_drafts(root) if draft["id"] == draft_id), None)


def _change(root, change):
    from . import workspace_store
    workspace = workspace_store.load(root)
    public = _public_routes(root)
    validate_catalogue_state(workspace["state"], public)
    changed, result = change(workspace, public)
    if changed:
        validate_catalogue_state(workspace["state"], public)
        workspace_store.save(root, workspace, workspace["revision"], workspace["mode"])
    return result


def _draft(workspace, draft_id, expected_revision=None):
    from . import workspace_store
    draft = workspace["state"].get("scholarshipDrafts", {}).get(_identifier(draft_id))
    if draft is None:
        raise ValueError("Scholarship draft was not found.")
    if expected_revision is not None and draft["revision"] != _revision(expected_revision):
        raise workspace_store.Conflict("The scholarship draft changed. Refresh before saving.")
    return draft


def _touch(draft):
    draft["revision"] += 1
    draft["updatedAt"] = _now()


def create_draft(root, draft_id, query, job_id, source_url=""):
    draft_id = _identifier(draft_id)
    query = _text(query, 1000, nonempty=True)
    job_id = _text(job_id, 150, nonempty=True)
    fields = validate_fields({"officialSourceUrl": source_url})

    def change(workspace, public):
        drafts = workspace["state"].setdefault("scholarshipDrafts", {})
        if draft_id in drafts:
            draft = drafts[draft_id]
            if draft["query"] != query or draft["jobId"] != job_id:
                raise ValueError("This draft identifier already belongs to another request.")
            return False, draft
        stamp = _now()
        draft = {"id": draft_id, "revision": 1, "status": "RESEARCHING", "query": query,
                 "jobId": job_id, "createdAt": stamp, "updatedAt": stamp,
                 "leadSourceUrl": source_url,
                 "fields": fields, "sources": [], "matches": []}
        drafts[draft_id] = draft
        return True, draft
    return _change(root, change)


def update_draft(root, draft_id, expected_revision, fields):
    _revision(expected_revision)
    fields = validate_fields(fields)

    def change(workspace, public):
        draft = _draft(workspace, draft_id, expected_revision)
        if draft["status"] not in ("READY", "FAILED"):
            raise ValueError("Wait for research to finish before editing the scholarship draft.")
        draft.update(fields=fields, status="READY", matches=_matches(fields, public + list(workspace["state"].get("localScholarships", {}).values())))
        draft.pop("error", None)
        _touch(draft)
        return True, draft
    return _change(root, change)


def retry_draft(root, draft_id, expected_revision, new_job_id):
    _revision(expected_revision)
    new_job_id = _text(new_job_id, 150, nonempty=True)

    def change(workspace, public):
        draft = _draft(workspace, draft_id, expected_revision)
        if draft["status"] not in ("FAILED", "READY"):
            raise ValueError("Only a completed or failed draft can be researched again.")
        if new_job_id == draft["jobId"]:
            raise ValueError("A new research job identifier is required.")
        draft.update(status="RESEARCHING", jobId=new_job_id)
        draft.pop("error", None)
        _touch(draft)
        return True, draft
    return _change(root, change)


def research_result(root, draft_id, job_id, fields, sources):
    fields = validate_fields(fields)
    sources = _sources(sources)
    if fields["officialSourceUrl"] and _url_key(fields["officialSourceUrl"]) not in {_url_key(source["url"]) for source in sources}:
        raise ValueError("The proposed official source must be a page actually read during this research.")

    def change(workspace, public):
        from . import workspace_store
        draft = _draft(workspace, draft_id)
        if draft["jobId"] != job_id or draft["status"] != "RESEARCHING":
            raise workspace_store.Conflict("This research result no longer matches the pending draft.")
        draft.update(fields=fields, sources=sources, status="READY",
                     matches=_matches(fields, public + list(workspace["state"].get("localScholarships", {}).values())))
        draft.pop("error", None)
        _touch(draft)
        return True, draft
    return _change(root, change)


def fail_draft(root, draft_id, job_id, error):
    error = _text(error, 1000, nonempty=True)

    def change(workspace, public):
        draft = _draft(workspace, draft_id)
        if draft["jobId"] != job_id or draft["status"] != "RESEARCHING":
            return False, draft
        draft.update(status="FAILED", error=error)
        _touch(draft)
        return True, draft
    return _change(root, change)


def _route(draft):
    fields = draft["fields"]
    route = {key: "UNKNOWN" for key in ROUTE_STRINGS}
    route.update(fields)
    route.update(id="local-" + draft["id"], local=True, secondarySourceUrl="",
                 seedStatus="OWNER_ACCEPTED_DRAFT_NOT_ELIGIBILITY_VERIFICATION",
                 currentCycleStatus="UNKNOWN", aiContentPolicy="UNKNOWN",
                 currentCycleEvidenceSummary="UNKNOWN — no target-cycle calendar evidence was added by this draft.",
                 reviewedAt=draft["updatedAt"][:10],
                 evidenceSources=[{key: value for key, value in source.items() if key != "title"} for source in draft["sources"]],
                 fieldReview={key: {"status": "DRAFT_NOT_ELIGIBILITY_VERIFICATION", "evidence": []}
                              for key in TEXT_FIELDS if key not in IDENTITY_FIELDS and key != "officialSourceUrl"})
    return route


def accept_draft(root, draft_id, expected_revision, fields=None):
    _revision(expected_revision)
    if fields is not None:
        fields = validate_fields(fields, require_identity=True)

    def change(workspace, public):
        draft = _draft(workspace, draft_id)
        # Repeated delivery of an accepted action is safe even with its old revision.
        if draft["status"] == "ACCEPTED":
            return False, {"draft": draft, "routeId": draft["acceptedRouteId"], "duplicate": False}
        _draft(workspace, draft_id, expected_revision)
        if draft["status"] != "READY":
            raise ValueError("Complete or edit the scholarship draft before adding it.")
        candidate = fields if fields is not None else validate_fields(draft["fields"], require_identity=True)
        matches = _matches(candidate, public + list(workspace["state"].get("localScholarships", {}).values()))
        exact = next((match for match in matches if match["kind"] == "EXACT"), None)
        if exact:
            return False, {"draft": draft, "routeId": exact["routeId"], "duplicate": True}
        draft.update(fields=candidate, matches=matches, status="ACCEPTED", acceptedRouteId="local-" + draft["id"])
        _touch(draft)
        workspace["state"].setdefault("localScholarships", {})[draft["acceptedRouteId"]] = _route(draft)
        return True, {"draft": draft, "routeId": draft["acceptedRouteId"], "duplicate": False}
    return _change(root, change)
