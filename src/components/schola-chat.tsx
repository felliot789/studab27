"use client";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { safeUrl } from "@/lib/schema";
import { Badge, dateTime, External, Icon } from "./ui";

type Message = { id: number; role: "user" | "assistant"; content: string; jobId: string; createdAt: string; meta: { model?: string; kind?: string; sources?: { url: string; retrievedAt: string; kind: string }[] } };
type Job = { id: string; kind: string; status: "QUEUED" | "RUNNING" | "DONE" | "FAILED"; error?: string; createdAt: string };
type Conversation = { messages: Message[]; jobs: Job[]; tools: { jobId: string; name: string; summary: string }[]; settings: { configured: boolean; model: string; contextAllowed: boolean; dailyCallLimit: number; searchProvider: string; backgroundEnabled: boolean }; callsToday: number; workerSeenAt?: string; workerHealth?: { state: "OK" | "UNSEEN" | "NEEDS_ATTENTION" }; search: { state: string; message: string } };
const suggestions = ["What needs my attention this week?", "Compare my most realistic engineering routes.", "What should I verify before choosing a route?"];
type ChatRoute = { id: string; institution: string; scholarshipName: string };

export default function ScholaChat({ route, embedded = false }: { route?: ChatRoute; embedded?: boolean } = {}) {
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
  const count = useRef(0);
  const initialScroll = useRef(true);
  const titleId = useId(), inputId = useId();
  const endpoint = route ? `/api/schola/chat?routeId=${encodeURIComponent(route.id)}` : "/api/schola/chat";
  const draftKey = route ? `studab27:schola-draft:${route.id}` : "studab27:schola-draft";
  const scrollToLatest = useCallback(() => {
    if (embedded && scroll.current) scroll.current.scrollTo({ top: scroll.current.scrollHeight, behavior: "instant" });
    else bottom.current?.scrollIntoView({ behavior: "instant", block: "end" });
    setShowNew(false);
  }, [embedded]);
  const refresh = useCallback(async () => {
    const response = await fetch(endpoint, { cache: "no-store" });
    if (response.status === 401) { window.location.assign("/login"); return; }
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Could not load this conversation.");
    setData(value); setOffline(false);
    if (value.messages.length !== count.current) {
      const nearBottom = embedded && scroll.current
        ? scroll.current.scrollHeight - scroll.current.clientHeight - scroll.current.scrollTop < 200
        : document.documentElement.scrollHeight - window.innerHeight - window.scrollY < 400;
      count.current = value.messages.length;
      if (initialScroll.current || nearBottom) requestAnimationFrame(scrollToLatest);
      else setShowNew(true);
      initialScroll.current = false;
    }
  }, [endpoint, embedded, scrollToLatest]);
  const active = data?.jobs.find(j => j.status === "QUEUED" || j.status === "RUNNING");
  useEffect(() => { refresh().catch(e => setError(e.message)); }, [refresh]);
  useEffect(() => {
    const tick = () => { if (!document.hidden) refresh().catch(() => setOffline(true)); };
    const timer = setInterval(tick, active ? 3000 : 20000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
  }, [refresh, active]);
  useEffect(() => {
    try { currentDraft.current = sessionStorage.getItem(draftKey) || ""; setDraft(currentDraft.current); } catch { /* Storage is optional. */ }
  }, [draftKey]);
  const edit = (value: string) => { currentDraft.current = value; setDraft(value); nonce.current = null; try { sessionStorage.setItem(draftKey, value); } catch { /* Storage is optional. */ } };
  const send = async (retry?: Job) => {
    if (sending || active || !data?.settings.configured || (!retry && !draft.trim())) return;
    setSending(true); setError("");
    const sentDraft = draft;
    const intent = retry ? `retry:${retry.id}` : `send:${sentDraft.trim()}`;
    if (nonce.current?.intent !== intent) nonce.current = { intent, id: crypto.randomUUID() };
    try {
      const response = await fetch("/api/schola/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...(retry ? { action: "retry", jobId: retry.id, id: nonce.current.id } : { action: "send", message: sentDraft.trim(), id: nonce.current.id }), ...(route ? { routeId: route.id } : {}) }) });
      if (response.status === 401) { window.location.assign("/login"); return; }
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Could not queue your message.");
      if (!retry && currentDraft.current === sentDraft) {
        let savedDraft = sentDraft;
        try { savedDraft = sessionStorage.getItem(draftKey) || ""; } catch { /* Storage is optional. */ }
        if (savedDraft === sentDraft) edit("");
      }
      nonce.current = null;
      await refresh();
      requestAnimationFrame(scrollToLatest);
    } catch (err) { setError(err instanceof Error ? err.message : "Connection failed. Your draft is still here."); }
    finally { setSending(false); }
  };
  const workerOnline = !!data?.workerSeenAt && Date.now() - Date.parse(data.workerSeenAt) < 4 * 60000;
  const needsAttention = data?.workerHealth?.state === "NEEDS_ATTENTION";
  const latestFailed = data?.jobs[0]?.status === "FAILED" ? data.jobs[0] : undefined;
  const Heading = embedded ? "h3" : "h1";
  const WelcomeHeading = embedded ? "h3" : "h2";
  const prompts = route ? [
    "What requirements and missing evidence should I check for this scholarship?",
    "Explain this scholarship’s funding and possible costs for my plan.",
    "Which official sources and dates should I verify next?",
  ] : suggestions;
  const conversation = <>
    <header className="chat-heading"><div><span className="chat-glyph" aria-hidden="true">✳</span><div><Heading id={titleId}>Schola</Heading><p>{route ? `${route.institution} · ${route.scholarshipName}` : "Scholarship research and application planning."}</p></div></div><Badge tone={workerOnline && !needsAttention ? "success" : "warning"}>{!workerOnline ? "Worker offline" : needsAttention ? "Needs attention" : "Online"}</Badge></header>
    <details className="connection-details">
      <summary><Icon name="shield" size={15} />{!data ? "Loading connection settings…" : data.settings.contextAllowed ? route ? "Using your context for this scholarship" : "Using your relevant project context" : "Fictional context only"}<Icon name="chevron" size={13} /></summary>
      {data ? <div>
        {route && <p>This private conversation is saved separately for this scholarship. Open general Schola from navigation to compare routes.</p>}
        <p><strong>Model:</strong> {data.settings.model}. {data.callsToday} / {data.settings.dailyCallLimit} calls today (UTC, shared across Schola).</p>
        <p><strong>Web search:</strong> {data.settings.searchProvider}. {data.search.message}</p>
        <p>Known official pages can be read directly. Search results and model answers still need evidence. Your relevant profile, budget, strategy and conversation may be sent through the configured model; credentials and private Calendar or Drive links are excluded.</p>
        <p>Model and search settings live in <code>private/schola.local.json</code>. {route ? "Background source reviews stay in general Schola." : data.settings.backgroundEnabled ? "New source changes can trigger a bounded review here." : "Background source review is off."} Schola’s tools read information; you make application and checklist changes.</p>
      </div> : <p>Loading connection settings…</p>}
    </details>
    {offline && <p className="chat-notice" role="status">Connection interrupted. Your queued work continues on the homelab. Reconnecting…</p>}
    {data && !data.settings.configured && <p className="chat-notice" role="status">Schola needs a model configuration before it can answer. Configure <code>private/schola.local.json</code> on the server, then reload this conversation. Your draft stays saved locally.</p>}
    {!data && !error && <div className="chat-loading" aria-label="Loading conversation"><div className="skeleton" /><div className="skeleton" /></div>}
    {data && !data.messages.length && <div className="chat-welcome"><span aria-hidden="true">✳</span><WelcomeHeading>{route ? "Your assistant for this scholarship" : "Scholarship research assistant"}</WelcomeHeading><p>{route ? "Review requirements, funding, your preparation and official sources for this scholarship. This conversation stays separate from general Schola." : "Compare scholarship routes, review requirements, or check official sources."}</p><div className="chat-suggestions">{prompts.map(s => <button key={s} onClick={() => { edit(s); input.current?.focus(); }}>{s}<Icon name="arrow" size={16} /></button>)}</div></div>}
    <div className="chat-messages" role="log" aria-label={route ? `Conversation with Schola about ${route.scholarshipName} at ${route.institution}` : "Conversation with Schola"} aria-live="polite" aria-relevant="additions">{data?.messages.map(message => <article key={message.id} className={`chat-message ${message.role}`}><header><strong>{message.role === "user" ? "You" : message.meta.kind === "source-review" ? "Schola · source review" : "Schola"}</strong><time dateTime={message.createdAt}>{dateTime(message.createdAt)}</time></header><MessageText text={message.content} />{!!message.meta.sources?.length && <details className="chat-sources"><summary>{message.meta.sources.length} source{message.meta.sources.length === 1 ? "" : "s"} consulted</summary>{message.meta.sources.map(source => <div key={source.url}><External href={source.url}>{new URL(source.url).hostname}</External><small>{source.kind} · {source.retrievedAt.slice(0, 10)}</small></div>)}</details>}</article>)}</div>
    {active && <div className="chat-working" role="status"><span className="status-dot running" /><div><strong>{active.status === "QUEUED" ? "Your message is saved in the queue." : "Processing your request."}</strong><p>{data?.tools.find(t => t.jobId === active.id)?.summary || (route ? "Loading context for this scholarship." : "Loading relevant project context.")} Processing continues if you {embedded ? "close this popup" : "close this page"}.</p>{!workerOnline && <p>The assistant worker is offline. Your message will remain queued until the worker is available.</p>}</div></div>}
    {latestFailed && <div className="chat-notice"><p>{latestFailed.error || "The saved request could not finish. You can retry it."}</p><button className="button secondary" disabled={sending || !!active || !data?.settings.configured} onClick={() => send(latestFailed)}><Icon name="refresh" size={15} />Retry saved message</button></div>}
    <div ref={bottom} className="chat-bottom" />
  </>;
  return <section className={`schola-corner${embedded ? " schola-embedded" : ""}`} aria-labelledby={titleId}>
    {embedded ? <div ref={scroll} className="chat-scroll">{conversation}</div> : conversation}
    {showNew && <button className="new-reply button secondary" onClick={scrollToLatest}>Jump to new reply<Icon name="arrow" size={15} /></button>}
    <form className="chat-composer" onSubmit={e => { e.preventDefault(); send(); }}><label className="sr-only" htmlFor={inputId}>{route ? `Message Schola about ${route.scholarshipName}` : "Message Schola"}</label><textarea ref={input} id={inputId} placeholder={route ? "Ask about this scholarship" : "Enter a scholarship research question"} rows={2} maxLength={6000} value={draft} onChange={e => edit(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} /><div><span>Draft saved locally. Select Send to submit.</span><button className="button primary" type="submit" disabled={sending || !!active || !draft.trim() || !data?.settings.configured}><span>{sending ? "Saving…" : "Send"}</span><Icon name="arrow" size={18} /></button></div>{error && <p role="alert" className="form-error">{error} <button type="button" className="text-button" onClick={() => refresh().then(() => setError("")).catch(e => setError(e.message))}>Reload</button></p>}</form>
  </section>;
}

function inline(text: string): ReactNode[] {
  return text.split(/(\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)|\*\*[^*\n]+\*\*|`[^`\n]+`|https?:\/\/[^\s<>]+)/g).map((part, index) => {
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link && safeUrl(link[2])) return <External key={index} href={link[2]}>{link[1]}</External>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    if (/^https?:\/\//.test(part) && safeUrl(part)) return <External key={index} href={part}>{part}</External>;
    return part;
  });
}
function MessageText({ text }: { text: string }) {
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
}
