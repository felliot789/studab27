"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { dateTime, Icon } from "./ui";

export type SessionStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "SUPERSEDED" | "STOPPED";
export type ResearchSession = {
  id: string;
  title: string;
  origin: "manual" | "watch";
  routeId: string | null;
  unread: boolean;
  status: SessionStatus;
  createdAt: string;
  updatedAt: string;
  jobId: string;
};

const sessionLabels: Record<SessionStatus, string> = {
  QUEUED: "Queued",
  RUNNING: "Investigating",
  DONE: "Complete",
  FAILED: "Interrupted",
  SUPERSEDED: "Redirected",
  STOPPED: "Stopped",
};
const endpoint = "/api/schola/chat";
const draftKey = "studab27:schola-investigation-draft";

export function researchSessionHref(id: string) {
  return `/schola?session=${encodeURIComponent(id)}`;
}

type SessionAction =
  | { action: "start-session"; id: string; message: string }
  | { action: "steer-session"; sessionId: string; id: string; message: string }
  | { action: "stop-session"; sessionId: string; jobId: string }
  | { action: "mark-session-read"; sessionId: string; updatedAt: string };

export async function researchAction(body: SessionAction): Promise<{ sessionId?: string; jobId?: string } | undefined> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 401) { window.location.assign("/login"); return; }
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "The investigation could not be updated.");
  return value;
}

function useResearchSessions(enabled = true) {
  const [index, setIndex] = useState<{ sessions: ResearchSession[]; settings: { configured: boolean } }>();
  const [error, setError] = useState("");
  const requestNumber = useRef(0);
  const reload = useCallback(async () => {
    const request = ++requestNumber.current;
    try {
      const response = await fetch(`${endpoint}?sessions=1`, { cache: "no-store" });
      const value = await response.json();
      if (!response.ok) throw new Error();
      if (request === requestNumber.current) { setIndex(value); setError(""); }
    } catch {
      if (request === requestNumber.current) setError("Research sessions are unavailable.");
    }
  }, []);
  useEffect(() => {
    if (!enabled) return;
    const visibleReload = () => { if (!document.hidden) void reload(); };
    visibleReload();
    const timer = setInterval(visibleReload, 30000);
    document.addEventListener("visibilitychange", visibleReload);
    return () => {
      requestNumber.current++;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visibleReload);
    };
  }, [enabled, reload]);
  return { index, error, reload };
}

export function ResearchSessions() {
  const [open, setOpen] = useState(false);
  const { index, error, reload } = useResearchSessions(open);
  const [draft, setDraft] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [pending, setPending] = useState(false);
  const attempt = useRef<{ message: string; id: string } | null>(null);
  const inputId = useId();
  const router = useRouter();
  useEffect(() => {
    try { setDraft(sessionStorage.getItem(draftKey) || ""); } catch { /* Storage is optional. */ }
  }, []);
  function edit(value: string) {
    setDraft(value);
    try { sessionStorage.setItem(draftKey, value); } catch { /* Storage is optional. */ }
  }
  async function start() {
    const message = draft.trim();
    if (pending || !message || !index?.settings.configured) return;
    if (attempt.current?.message !== message) attempt.current = { message, id: crypto.randomUUID() };
    setPending(true);
    setSubmitError("");
    try {
      const result = await researchAction({ action: "start-session", ...attempt.current });
      if (!result) return;
      if (!result.sessionId) throw new Error("The investigation could not be opened.");
      edit("");
      router.push(researchSessionHref(result.sessionId));
    } catch (cause) {
      setSubmitError(cause instanceof Error ? cause.message : "The investigation could not be started.");
    } finally {
      setPending(false);
    }
  }
  return <details className="connection-details schola-sessions" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Research sessions<Icon name="chevron" size={13} /></summary>
    <div>
      {error && <p className="form-error" role="status">{error} <button type="button" className="text-button" onClick={reload}>Reload</button></p>}
      {!index && !error && <p role="status">Loading research sessions…</p>}
      <form className="schola-start-form" onSubmit={event => { event.preventDefault(); void start(); }}>
        <label htmlFor={inputId}>Investigation brief</label>
        <textarea id={inputId} rows={2} maxLength={6000} value={draft} onChange={event => edit(event.target.value)} disabled={pending} placeholder="Describe a lead, comparison, or deadline to investigate" />
        <button className="button secondary" type="submit" disabled={pending || !index?.settings.configured || !draft.trim()}>{pending ? "Opening investigation…" : "Start investigation"}</button>
        {submitError && <p className="form-error" role="alert">{submitError}</p>}
      </form>
      {!!index?.sessions.length && <ul className="schola-session-list" aria-label="Recent research sessions">
        {index.sessions.map(session => <li key={session.id}>
          <Link href={researchSessionHref(session.id)}>{session.title}</Link>
          <small>{session.origin === "watch" && "Background · "}{sessionLabels[session.status]} · <time dateTime={session.updatedAt}>{dateTime(session.updatedAt)}</time></small>
        </li>)}
      </ul>}
    </div>
  </details>;
}

export function ScholaFindingBanner() {
  const { index, reload } = useResearchSessions();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ id: string; message: string }>();
  const unread = index?.sessions.filter(session => session.origin === "watch" && session.unread) || [];
  const session = unread[0];
  if (!session) return null;
  async function acknowledge(item: ResearchSession) {
    if (pending) return;
    setPending(true);
    setError(undefined);
    try {
      await researchAction({ action: "mark-session-read", sessionId: item.id, updatedAt: item.updatedAt });
      await reload();
    } catch (cause) {
      setError({ id: item.id, message: cause instanceof Error ? cause.message : "The finding could not be marked as read." });
    } finally {
      setPending(false);
    }
  }
  return <section className="schola-finding-banner" aria-label="Schola findings">
    <div>
      <strong>{session.title}</strong>
      <small>Schola · {sessionLabels[session.status]}{unread.length > 1 && ` · ${unread.length} unread`}</small>
      {error?.id === session.id && <p className="form-error" role="alert">{error.message}</p>}
    </div>
    <div className="schola-finding-actions">
      <Link className="text-button" href={researchSessionHref(session.id)}>Review</Link>
      <button type="button" className="text-button" disabled={pending} onClick={() => acknowledge(session)}>{pending ? "Saving…" : "Mark as read"}</button>
    </div>
  </section>;
}
