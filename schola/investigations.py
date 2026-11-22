"""Durable research-session records. The assistant worker still runs one job at a time."""
import json
import re
import uuid

from .watcher import now


SCHEMA = (
    """CREATE TABLE research_sessions(
      id TEXT PRIMARY KEY NOT NULL, title TEXT NOT NULL,
      origin TEXT NOT NULL CHECK(origin IN ('manual','watch')), route_id TEXT, topic TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, unread INTEGER NOT NULL CHECK(unread IN (0,1)),
      CHECK((origin='watch' AND route_id IS NOT NULL AND topic IS NOT NULL) OR
            (origin='manual' AND route_id IS NULL AND topic IS NULL)))""",
    """CREATE UNIQUE INDEX research_watch_topic ON research_sessions(route_id,topic) WHERE origin='watch'""",
    """CREATE TABLE research_jobs(
      job_id TEXT PRIMARY KEY NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
      session_id TEXT NOT NULL REFERENCES research_sessions(id) ON DELETE RESTRICT,
      outcome TEXT CHECK(outcome IN ('SUPERSEDED','STOPPED')))""",
    "CREATE INDEX research_jobs_session ON research_jobs(session_id)",
    """CREATE TABLE research_findings(
      tool_id INTEGER PRIMARY KEY REFERENCES tools(id) ON DELETE RESTRICT,
      body TEXT NOT NULL CHECK(json_valid(body)))""",
)

SESSION_SELECT = """SELECT s.id,s.title,s.origin,s.route_id AS routeId,s.unread,s.created_at AS createdAt,
    s.updated_at AS updatedAt,j.id AS jobId,COALESCE(r.outcome,j.status) AS status
    FROM research_sessions AS s JOIN research_jobs AS r ON r.session_id=s.id JOIN jobs AS j ON j.id=r.job_id
    WHERE j.rowid=(SELECT MAX(p.rowid) FROM jobs AS p JOIN research_jobs AS q ON q.job_id=p.id WHERE q.session_id=s.id)"""


class Interrupted(Exception):
    """A saved redirect or stop ended the old job."""


def identifier(value=None):
    if value is None:
        return str(uuid.uuid4())
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{12,80}", value):
        raise ValueError("Invalid investigation or message identifier.")
    return value


def message(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 6000:
        raise ValueError("Write a message of 1–6000 characters.")
    return value.strip()


def describe(connection, session_id):
    if session_id is None:
        raise ValueError("Open a research session first.")
    row = connection.execute(SESSION_SELECT + " AND s.id=?", (identifier(session_id),)).fetchone()
    if row is None:
        raise ValueError("Research session unavailable.")
    return dict(row) | {"unread": bool(row["unread"])}


def recent_sessions(connection):
    return [dict(row) | {"unread": bool(row["unread"])} for row in connection.execute(
        SESSION_SELECT + " ORDER BY s.unread DESC,s.updated_at DESC LIMIT 30")]


def current_job(connection, job_id):
    if connection.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0] != "RUNNING":
        raise Interrupted()


def end_job(connection, job_id, outcome, timestamp):
    changed = connection.execute("UPDATE jobs SET status='DONE',updated_at=? WHERE id=? AND status IN ('QUEUED','RUNNING')",
                                 (timestamp, job_id)).rowcount
    if changed:
        connection.execute("UPDATE research_jobs SET outcome=? WHERE job_id=?", (outcome, job_id))


def queue(connection, prompt, job_id=None, *, session_id=None, watch=None):
    """Enqueue one turn and supersede any unfinished turn in the same transaction."""
    prompt, job_id = message(prompt), identifier(job_id)
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing = connection.execute("""SELECT j.prompt,r.session_id FROM jobs AS j
            LEFT JOIN research_jobs AS r ON r.job_id=j.id WHERE j.id=?""", (job_id,)).fetchone()
        if existing:
            intended_session = session_id if session_id is not None else job_id
            if watch is not None:
                row = connection.execute("SELECT id FROM research_sessions WHERE origin='watch' AND route_id=? AND topic=?",
                                         (watch["routeId"], watch["topic"])).fetchone()
                intended_session = row["id"] if row else None
            if existing["session_id"] != intended_session or intended_session is None or existing["prompt"] != prompt:
                raise ValueError("That message identifier is already in use.")
            connection.execute("COMMIT")
            return {"sessionId": intended_session, "jobId": job_id}

        stamp = now()
        if watch is not None:
            from_watch = connection.execute("SELECT id FROM research_sessions WHERE origin='watch' AND route_id=? AND topic=?",
                                            (watch["routeId"], watch["topic"])).fetchone()
            session_id = from_watch["id"] if from_watch else None
        if session_id is None:
            session_id = job_id
            title = watch["title"] if watch else " ".join(prompt.split())[:120]
            connection.execute("INSERT INTO research_sessions VALUES(?,?,?,?,?,?,?,?)", (
                session_id, title, "watch" if watch else "manual", watch["routeId"] if watch else None,
                watch["topic"] if watch else None, stamp, stamp, int(watch is not None)))
            route_id = watch["routeId"] if watch else None
        else:
            previous = describe(connection, session_id)
            route_id = previous["routeId"]
            if watch is not None and previous["status"] in ("QUEUED", "RUNNING"):
                raise ValueError("A research session is already investigating this change.")
            end_job(connection, previous["jobId"], "SUPERSEDED", stamp)
            connection.execute("UPDATE research_sessions SET updated_at=?,unread=? WHERE id=?",
                               (stamp, int(watch is not None), session_id))

        connection.execute("INSERT INTO jobs VALUES(?,?,?,'QUEUED',NULL,?,?)",
                           (job_id, "source-review" if watch else "investigation", prompt, stamp, stamp))
        if route_id is not None:
            connection.execute("INSERT INTO job_scopes VALUES(?,?)", (job_id, route_id))
        connection.execute("INSERT INTO research_jobs(job_id,session_id) VALUES(?,?)", (job_id, session_id))
        meta = {"kind": "watch-trigger", "watchObservation": watch["observation"]} if watch else {}
        connection.execute("INSERT INTO messages(role,content,job_id,created_at,meta,route_id) VALUES('user',?,?,?,?,?)",
                           (prompt, job_id, stamp, json.dumps(meta, ensure_ascii=False), route_id))
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return {"sessionId": session_id, "jobId": job_id}


def stop(connection, session_id, job_id):
    connection.execute("BEGIN IMMEDIATE")
    try:
        session = describe(connection, session_id)
        if session["jobId"] != job_id:
            raise ValueError("This investigation changed. Open its current status before stopping work.")
        stamp = now()
        end_job(connection, job_id, "STOPPED", stamp)
        if session["status"] in ("QUEUED", "RUNNING"):
            connection.execute("UPDATE research_sessions SET updated_at=? WHERE id=?", (stamp, session_id))
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return {"ok": True}


def mark_read(connection, session_id, observed_at):
    describe(connection, session_id)
    if not isinstance(observed_at, str):
        raise ValueError("Open the current finding before marking it as read.")
    updated = connection.execute("UPDATE research_sessions SET unread=0 WHERE id=? AND updated_at=?",
                                 (session_id, observed_at)).rowcount
    return {"ok": True, "updated": bool(updated)}


def timeline(connection, session):
    """Bound one response, retain all rows for later history access."""
    session_id = session["id"]
    messages = [dict(row) for row in connection.execute("""SELECT * FROM (
        SELECT m.id,m.role,m.content,m.job_id AS jobId,m.created_at AS createdAt,m.meta
        FROM research_jobs AS r JOIN messages AS m ON m.job_id=r.job_id
        WHERE r.session_id=? ORDER BY m.id DESC LIMIT 31) ORDER BY id""", (session_id,))]
    jobs = [dict(row) for row in connection.execute("""SELECT j.id,j.kind,COALESCE(r.outcome,j.status) AS status,
        j.error,j.created_at AS createdAt,j.updated_at AS updatedAt FROM research_jobs AS r JOIN jobs AS j ON j.id=r.job_id
        WHERE r.session_id=? ORDER BY j.rowid DESC LIMIT 41""", (session_id,))]
    tools = [dict(row) for row in connection.execute("""SELECT t.job_id AS jobId,t.name,t.summary,
        t.created_at AS createdAt,f.body AS finding FROM research_jobs AS r JOIN tools AS t ON t.job_id=r.job_id
        LEFT JOIN research_findings AS f ON f.tool_id=t.id WHERE r.session_id=? ORDER BY t.id DESC LIMIT 81""", (session_id,))]
    for tool in tools:
        raw = tool.pop("finding")
        if raw is not None:
            tool["finding"] = json.loads(raw)
    return (messages[-30:], jobs[:40], tools[:80], len(messages) > 30 or len(jobs) > 40 or len(tools) > 80)


def review_citations(text, current, earlier):
    """Only expose hyperlinks backed by a successful read in the session."""
    sources = {finding["url"].split("#")[0].rstrip("/"): {
        "url": finding["url"], "retrievedAt": finding["retrievedAt"], "sha256": finding["sha256"],
        "kind": "Earlier session read"} for finding in earlier}
    for source in current.values():
        if source["kind"] != "Read live":
            continue
        for url in (source["url"], *source.get("requestedUrls", [])):
            sources[url.split("#")[0].rstrip("/")] = source
    cited, omitted = {}, False

    def candidate(url):
        nonlocal omitted
        support = sources.get(url.split("#")[0].rstrip("/"))
        if support is None:
            omitted = True
            return False
        cited[support["url"]] = support
        return True

    def markdown_link(match):
        title, url = match.group(1), match.group(2)
        if not candidate(url):
            return title + " [unverified link omitted]"
        return match[0]

    def bare_link(match):
        url = match[0].rstrip(".,;:!?")
        return match[0] if candidate(url) else "[unverified link omitted]" + match[0][len(url):]

    # Match complete Markdown links before bare URLs so an unsupported link
    # cannot leave a broken bracket or link destination behind.
    def link(match):
        if match[1] is not None:
            return markdown_link(match)
        if match[3] is not None:
            return match[3] if candidate(match[3]) else "[unverified link omitted]"
        return bare_link(match)

    text = re.sub(r"\[([^\]\n]*)\]\((https?://[^\s)<>]+)\)|\x60(https?://[^\x60\s<>]+)\x60|https?://[^\s<>()\[\]\x22'\x60]+",
                  link, text, flags=re.IGNORECASE)
    if not cited:
        text = "**Evidence incomplete.** This answer cites no source read in this investigation.\n\n" + text
    if omitted:
        text = "**Source check.** Some links in this answer were omitted because the session did not read them.\n\n" + text
    return text, list(cited.values())[:15]
