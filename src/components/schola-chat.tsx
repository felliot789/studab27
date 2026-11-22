"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { memo, useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { safeUrl } from "@/lib/schema";
import { Badge, dateTime, External, Icon } from "./ui";
import ScholarshipDraftsButton from "./scholarship-drafts";
import { ResearchSessions, researchAction, type ResearchSession, type SessionStatus } from "./schola-sessions";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  jobId: string;
  createdAt: string;
  meta: {
    kind?: string;
    sources?: { url: string; retrievedAt: string; kind: string }[];
    watchObservation?: { url: string; excerpt: string; at: string };
  };
};
type Job = { id: string; kind: string; status: SessionStatus; error?: string; createdAt: string; updatedAt?: string };
type ResearchTool = {
  jobId: string;
  name: string;
  summary: string;
  createdAt?: string;
  finding?: { url: string; excerpt: string; retrievedAt: string; sha256: string };
};
type Conversation = {
  messages: Message[];
  jobs: Job[];
  tools: ResearchTool[];
  session?: ResearchSession;
  historyTruncated?: boolean;
  settings: { configured: boolean; model: string; contextAllowed: boolean; dailyCallLimit: number; searchProvider: string; backgroundEnabled: boolean };
  callsToday: number;
  workerSeenAt?: string;
  workerHealth?: { state: "OK" | "UNSEEN" | "NEEDS_ATTENTION" };
  search: { state: string; message: string };
};
const suggestions = ["Which application deadlines and tasks are due this week?", "Compare the tracked engineering routes and their scholarship outlooks.", "What evidence is needed before choosing a route?"];
type ChatRoute = { id: string; institution: string; scholarshipName: string };

export default function ScholaChat({ route, embedded = false }: { route?: ChatRoute; embedded?: boolean } = {}) {
  return route || embedded ? <ChatConversation route={route} embedded={embedded} /> : <ScholaHome />;
}

function ScholaHome() {
  const sessionId = useSearchParams().get("session") || undefined;
  return <ChatConversation key={sessionId ? `session:${sessionId}` : "general"} sessionId={sessionId} />;
}

function ChatConversation({ route, embedded = false, sessionId }: { route?: ChatRoute; embedded?: boolean; sessionId?: string }) {
  const [data, setData] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [offline, setOffline] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const currentDraft = useRef("");
  const nonce = useRef<{ intent: string; id: string } | null>(null);
  const lastMessage = useRef(0);
  const requestNumber = useRef(0);
  const polling = useRef(false);
  const initialScroll = useRef(true);
  const titleId = useId(), inputId = useId();
  const endpoint = "/api/schola/chat" + (sessionId ? `?sessionId=${encodeURIComponent(sessionId)}` : route ? `?routeId=${encodeURIComponent(route.id)}` : "");
  const draftKey = "studab27:schola-draft" + (sessionId ? `:session:${sessionId}` : route ? `:${route.id}` : "");
  const scrollToLatest = useCallback(() => {
    if (embedded && scroll.current) scroll.current.scrollTo({ top: scroll.current.scrollHeight, behavior: "instant" });
    else bottom.current?.scrollIntoView({ behavior: "instant", block: "end" });
    setShowNew(false);
  }, [embedded]);
  const refresh = useCallback(async () => {
    const request = ++requestNumber.current;
    const response = await fetch(endpoint, { cache: "no-store" });
    if (request !== requestNumber.current) return;
    if (response.status === 401) { window.location.assign("/login"); return; }
    const value = await response.json();
    if (request !== requestNumber.current) return;
    if (!response.ok) throw new Error(value.error || "Could not load this conversation.");
    setData(value); setOffline(false);
    const latest = value.messages.at(-1)?.id || 0;
    if (latest !== lastMessage.current) {
      const nearBottom = embedded && scroll.current
        ? scroll.current.scrollHeight - scroll.current.clientHeight - scroll.current.scrollTop < 200
        : document.documentElement.scrollHeight - window.innerHeight - window.scrollY < 400;
      lastMessage.current = latest;
      if (initialScroll.current || nearBottom) requestAnimationFrame(scrollToLatest);
      else setShowNew(true);
      initialScroll.current = false;
    }
  }, [endpoint, embedded, scrollToLatest]);
  const active = data?.jobs.find(job => job.status === "QUEUED" || job.status === "RUNNING");
  const isActive = !!active;
  const attemptStartedAt = active?.updatedAt ? Date.parse(active.updatedAt) : NaN;
  const lastResearchStep = active?.status === "RUNNING" && Number.isFinite(attemptStartedAt)
    ? data?.tools.find(tool => tool.jobId === active.id && !!tool.createdAt && Date.parse(tool.createdAt) >= attemptStartedAt)
    : undefined;
  useEffect(() => {
    refresh().catch(e => setError(e.message));
    return () => { requestNumber.current++; };
  }, [refresh]);
  useEffect(() => {
    const tick = () => {
      if (document.hidden || polling.current) return;
      polling.current = true;
      refresh().catch(() => setOffline(true)).finally(() => { polling.current = false; });
    };
    const timer = setInterval(tick, isActive ? 3000 : 20000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
  }, [refresh, isActive]);
  useEffect(() => {
    try { currentDraft.current = sessionStorage.getItem(draftKey) || ""; setDraft(currentDraft.current); } catch { /* Storage is optional. */ }
  }, [draftKey]);
  const edit = (value: string) => { currentDraft.current = value; setDraft(value); nonce.current = null; try { sessionStorage.setItem(draftKey, value); } catch { /* Storage is optional. */ } };
  const send = async (retry?: Job) => {
    if (sending || (active && !sessionId) || !data?.settings.configured || (!retry && !draft.trim())) return;
    setSending(true); setError("");
    const sentDraft = draft;
    const intent = retry ? `retry:${retry.id}` : `send:${sentDraft.trim()}`;
    if (nonce.current?.intent !== intent) nonce.current = { intent, id: crypto.randomUUID() };
    try {
      if (sessionId) {
        if (!await researchAction({ action: "steer-session", sessionId, message: sentDraft.trim(), id: nonce.current.id })) return;
      } else {
        const response = await fetch("/api/schola/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...(retry ? { action: "retry", jobId: retry.id, id: nonce.current.id } : { action: "send", message: sentDraft.trim(), id: nonce.current.id }), ...(route ? { routeId: route.id } : {}) }) });
        if (response.status === 401) { window.location.assign("/login"); return; }
        const value = await response.json();
        if (!response.ok) throw new Error(value.error || "Could not queue the message.");
      }
      if (!retry && currentDraft.current === sentDraft) {
        let savedDraft = sentDraft;
        try { savedDraft = sessionStorage.getItem(draftKey) || ""; } catch { /* Storage is optional. */ }
        if (savedDraft === sentDraft) edit("");
      }
      nonce.current = null;
      await refresh();
      requestAnimationFrame(scrollToLatest);
    } catch (err) { setError(err instanceof Error ? err.message : "Connection failed. Draft retained."); }
    finally { setSending(false); }
  };
  async function stop() {
    if (!sessionId || !active || sending) return;
    setSending(true); setError("");
    try {
      if (await researchAction({ action: "stop-session", sessionId, jobId: active.id })) await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The investigation could not be stopped.");
    } finally {
      setSending(false);
    }
  }
  const workerOnline = !!data?.workerSeenAt && Date.now() - Date.parse(data.workerSeenAt) < 4 * 60000;
  const needsAttention = data?.workerHealth?.state === "NEEDS_ATTENTION";
  const latestFailed = data?.jobs[0]?.status === "FAILED" ? data.jobs[0] : undefined;
  const stopped = data?.jobs[0]?.status === "STOPPED";
  const redirected = active?.status === "QUEUED" && data?.jobs[1]?.status === "SUPERSEDED";
  const Heading = embedded ? "h3" : "h1";
  const WelcomeHeading = embedded ? "h3" : "h2";
  const prompts = route ? [
    "What requirements and missing evidence need checking for this scholarship?",
    "Explain this scholarship’s funding and estimated costs.",
    "Which official sources and dates need verification?",
  ] : suggestions;
  const title = sessionId ? data?.session?.title || "Investigation" : "Schola";
  const subtitle = sessionId ? data?.session?.origin === "watch" ? "Background investigation" : "Research session"
    : route ? `${route.institution} · ${route.scholarshipName}` : "Scholarship research and application planning.";
  const placeholder = sessionId ? active ? "Redirect the investigation" : "Send a follow-up"
    : route ? "Ask about this scholarship" : "Enter a scholarship research question";
  const conversation = <>
    {sessionId && <Link className="text-button schola-session-back" href="/schola"><Icon name="back" size={16} />Schola</Link>}
    <header className={sessionId ? "chat-heading schola-session-heading" : "chat-heading"}><div><span className="chat-glyph" aria-hidden="true">✳</span><div><Heading id={titleId}>{title}</Heading><p>{subtitle}</p></div></div>{data && <Badge tone={workerOnline && !needsAttention ? "success" : "warning"}>{!workerOnline ? "Worker offline" : needsAttention ? "Needs attention" : "Online"}</Badge>}</header>
    {!route && !sessionId && <><ResearchSessions /><div className="schola-drafts-entry"><ScholarshipDraftsButton /><p>Research a new opportunity or review saved scholarship drafts.</p></div></>}
    <details className="connection-details">
      <summary><Icon name="shield" size={15} />{!data ? "Loading connection settings…" : data.session?.origin === "watch" ? "Public source context" : data.settings.contextAllowed ? route ? "Scholarship context enabled" : "Project context enabled" : "Fictional context only"}<Icon name="chevron" size={13} /></summary>
      {data ? <div>
        {route && <p>This private conversation is saved separately for this scholarship. Open general Schola from navigation to compare routes.</p>}
        <p><strong>Model:</strong> {data.settings.model}. {data.callsToday} / {data.settings.dailyCallLimit} calls today (UTC, shared across Schola).</p>
        <p><strong>Web search:</strong> {data.settings.searchProvider}. {data.search.message}</p>
        <p>{data.session?.origin === "watch"
          ? "Background investigations use public scholarship sources and instructions entered in this session."
          : "Known official pages can be read directly. Search results and model answers still need evidence. Relevant profile, budget, strategy and conversation data may be sent through the configured model; credentials and private Calendar or Drive links are excluded."}</p>
        <p>Model and search settings live in <code>private/schola.local.json</code>. {data.settings.backgroundEnabled ? "Changes to tracked sources can open a research session." : "Background source review is off."} Schola’s tools read information. Application and checklist changes require explicit actions.</p>
      </div> : <p>Loading connection settings…</p>}
    </details>
    {offline && <p className="chat-notice" role="status">Connection interrupted. Queued requests remain saved. Reconnecting…</p>}
    {data && !data.settings.configured && <p className="chat-notice" role="status">Schola needs a model configuration before it can answer. Configure <code>private/schola.local.json</code> on the server, then reload this conversation. Draft saved locally.</p>}
    {!data && !error && <div className="chat-loading" aria-label="Loading conversation"><div className="skeleton" /><div className="skeleton" /></div>}
    {data && !sessionId && !data.messages.length && <div className="chat-welcome"><span className="chat-glyph" aria-hidden="true">✳</span><WelcomeHeading>{route ? "Scholarship research" : "Scholarship research assistant"}</WelcomeHeading><p>{route ? "Review requirements, funding, preparation and official sources for this scholarship. This conversation stays separate from general Schola." : "Compare scholarship routes, review requirements, or check official sources."}</p><div className="chat-suggestions">{prompts.map(s => <button key={s} onClick={() => { edit(s); input.current?.focus(); }}>{s}<Icon name="arrow" size={16} /></button>)}</div></div>}
    {data?.historyTruncated && <p className="chat-notice">Showing the latest messages and research steps in this session.</p>}
    <div className="chat-messages" role="log" aria-label={route ? `Conversation with Schola about ${route.scholarshipName} at ${route.institution}` : "Conversation with Schola"} aria-live="polite" aria-relevant="additions">
      {data?.messages.map(message => <ConversationMessage key={message.id} message={message} />)}
    </div>
    {sessionId && !!data?.tools.length && <ResearchActivity tools={data.tools} jobs={data.jobs} />}
    {active && <div className="chat-working">
      <span className="status-dot running" />
      <div>
        <div role="status">
          <strong>{active.status === "QUEUED" ? redirected ? "Direction saved." : "Message queued." : "Processing request."}</strong>
          {active.status === "QUEUED" ? <p>{redirected ? "The next research step will use this direction." : "Waiting for the assistant worker."}</p>
            : lastResearchStep ? <p>Last research step: {lastResearchStep.summary}</p> : <p>Research is in progress. Completed steps will appear here.</p>}
          <p>Processing continues after {embedded ? "this popup closes" : "this page closes"}.</p>
          {!workerOnline && <p>The assistant worker is offline. The saved request remains available.</p>}
        </div>
        {sessionId && <button className="button quiet schola-stop" type="button" disabled={sending} onClick={stop}>Stop investigation</button>}
      </div>
    </div>}
    {sessionId && stopped && <p className="chat-notice" role="status">Investigation stopped. Findings are saved. Send a follow-up to continue.</p>}
    {latestFailed && <div className="chat-notice"><p>{latestFailed.error || "The saved request could not finish."}</p>{sessionId ? <p>Send a follow-up to continue the investigation.</p> : <button className="button secondary" disabled={sending || !!active || !data?.settings.configured} onClick={() => send(latestFailed)}><Icon name="refresh" size={15} />Retry saved message</button>}</div>}
    <div ref={bottom} className="chat-bottom" />
  </>;
  return <section className={`schola-corner${embedded ? " schola-embedded" : ""}`} aria-labelledby={titleId}>
    {embedded ? <div ref={scroll} className="chat-scroll">{conversation}</div> : conversation}
    {showNew && <button className="new-reply button secondary" onClick={scrollToLatest}>Jump to new reply</button>}
    <form className="chat-composer" onSubmit={e => { e.preventDefault(); send(); }}>
      <label className="sr-only" htmlFor={inputId}>{sessionId ? "Investigation direction" : route ? `Message Schola about ${route.scholarshipName}` : "Message Schola"}</label>
      <textarea ref={input} id={inputId} placeholder={placeholder} rows={2} maxLength={6000} value={draft} onChange={e => edit(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
      <div>
        <span>{sessionId && active ? "Direction applies before the next research step." : "Draft saved locally."}</span>
        <button className="button primary" type="submit" disabled={sending || (!!active && !sessionId) || !draft.trim() || !data?.settings.configured}><span>{sending ? "Saving…" : sessionId && active ? "Redirect" : "Send"}</span><Icon name="arrow" size={18} /></button>
      </div>
      {error && <p role="alert" className="form-error">{error} <button type="button" className="text-button" onClick={() => refresh().then(() => setError("")).catch(e => setError(e.message))}>Reload</button></p>}
    </form>
  </section>;
}

function ConversationMessage({ message }: { message: Message }) {
  const author = message.meta.kind === "watch-trigger" ? "Source monitor" : message.role === "user" ? "User"
    : message.meta.kind === "source-review" ? "Schola · source review" : "Schola";
  const sources = message.meta.sources?.filter(source => safeUrl(source.url)) || [];
  const observation = message.meta.watchObservation;
  return <article className={`chat-message ${message.role}`}>
    <header><strong>{author}</strong><time dateTime={message.createdAt}>{dateTime(message.createdAt)}</time></header>
    <MessageText text={message.content} />
    {observation && <SourceExcerpt label="Source monitor excerpt" url={observation.url} text={observation.excerpt} at={observation.at} />}
    {!!sources.length && <details className="chat-sources"><summary>{sources.length} source{sources.length === 1 ? "" : "s"} consulted</summary>
      {sources.map(source => <div key={source.url}><External href={source.url}>{new URL(source.url).hostname}</External><small>{source.kind} · {source.retrievedAt.slice(0, 10)}</small></div>)}
    </details>}
  </article>;
}

function ResearchActivity({ tools, jobs }: { tools: ResearchTool[]; jobs: Job[] }) {
  const prior = new Set(jobs.filter(job => job.status === "SUPERSEDED").map(job => job.id));
  return <details className="connection-details schola-activity">
    <summary>Research activity · {tools.length} {tools.length === 1 ? "step" : "steps"}<Icon name="chevron" size={13} /></summary>
    <ol>
      {[...tools].sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || "")).map((tool, index) => <li key={`${tool.jobId}:${index}`}>
        <strong>{tool.summary}</strong>
        {tool.createdAt && <time dateTime={tool.createdAt}>{dateTime(tool.createdAt)}</time>}
        {prior.has(tool.jobId) && <small>Earlier direction</small>}
        {tool.finding && <SourceExcerpt label="Source excerpt" url={tool.finding.url} text={tool.finding.excerpt} at={tool.finding.retrievedAt} />}
      </li>)}
    </ol>
  </details>;
}

function SourceExcerpt({ label, url, text, at }: { label: string; url: string; text: string; at: string }) {
  if (!safeUrl(url)) return null;
  return <details className="chat-sources schola-source-excerpt">
    <summary>{label}</summary>
    <External href={url}>{new URL(url).hostname}</External>
    <blockquote>{text}</blockquote>
    <time dateTime={at}>{dateTime(at)}</time>
  </details>;
}

function inline(text: string): ReactNode[] {
  return text.split(/(\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*\n]+\*\*|`[^`\n]+`|https?:\/\/[^\s<>]+)/g).map((part, index) => {
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link && safeUrl(link[2])) return <External key={index} href={link[2]}>{link[1]}</External>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    if (/^https?:\/\//.test(part)) {
      const url = part.replace(/[.,;:!?)]*$/, "");
      if (safeUrl(url)) return [<External key={index} href={url}>{url}</External>, part.slice(url.length)];
    }
    return part;
  });
}
const MessageText = memo(function MessageText({ text }: { text: string }) {
  const lines = text.split("\n"), blocks: ReactNode[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const numbered = /^\d+[.)]\s/.test(lines[i]);
    if (numbered || /^[-*]\s/.test(lines[i])) {
      const items: ReactNode[] = [];
      while (i < lines.length && (numbered ? /^\d+[.)]\s/.test(lines[i]) : /^[-*]\s/.test(lines[i]))) { items.push(<li key={i}>{inline(lines[i].replace(/^(?:\d+[.)]|[-*])\s+/, ""))}</li>); i++; }
      blocks.push(numbered ? <ol key={i}>{items}</ol> : <ul key={i}>{items}</ul>); i--; continue;
    }
    blocks.push(/^#{1,6}\s/.test(lines[i]) ? <h3 key={i}>{inline(lines[i].replace(/^#+\s/, ""))}</h3> : <p key={i}>{inline(lines[i])}</p>);
  }
  return <div className="chat-text">{blocks}</div>;
});
