"use client";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { safeUrl } from "@/lib/schema";
import { Badge, dateTime, External, Icon } from "./ui";

type Message = { id: number; role: "user" | "assistant"; content: string; jobId: string; createdAt: string; meta: { model?: string; kind?: string; sources?: { url: string; retrievedAt: string; kind: string }[] } };
type Job = { id: string; kind: string; status: "QUEUED" | "RUNNING" | "DONE" | "FAILED"; error?: string; createdAt: string };
type Conversation = { messages: Message[]; jobs: Job[]; tools: { jobId: string; name: string; summary: string }[]; settings: { configured: boolean; model: string; contextAllowed: boolean; dailyCallLimit: number; searchProvider: string; backgroundEnabled: boolean }; callsToday: number; workerSeenAt?: string; search: { state: string; message: string } };
const suggestions = ["What needs my attention this week?", "Compare my most realistic engineering routes.", "What should I verify before choosing a route?"];

export default function ScholaChat() {
  const [data, setData] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [offline, setOffline] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const nonce = useRef<string | null>(null);
  const count = useRef(0);
  const initialScroll = useRef(true);
  const refresh = useCallback(async () => {
    const response = await fetch("/api/schola/chat", { cache: "no-store" });
    if (response.status === 401) { window.location.assign("/login"); return; }
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Could not load this conversation.");
    setData(value); setOffline(false);
    if (value.messages.length !== count.current) {
      const nearBottom = document.documentElement.scrollHeight - window.innerHeight - window.scrollY < 400;
      count.current = value.messages.length;
      if (initialScroll.current || nearBottom) requestAnimationFrame(() => bottom.current?.scrollIntoView({ behavior: "instant", block: "end" }));
      else setShowNew(true);
      initialScroll.current = false;
    }
  }, []);
  const active = data?.jobs.find(j => j.status === "QUEUED" || j.status === "RUNNING");
  useEffect(() => { refresh().catch(e => setError(e.message)); }, [refresh]);
  useEffect(() => {
    const tick = () => { if (!document.hidden) refresh().catch(() => setOffline(true)); };
    const timer = setInterval(tick, active ? 3000 : 20000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
  }, [refresh, active]);
  useEffect(() => {
    try { setDraft(sessionStorage.getItem("studab27:schola-draft") || ""); } catch { /* Storage is optional. */ }
  }, []);
  const edit = (value: string) => { setDraft(value); nonce.current = null; try { sessionStorage.setItem("studab27:schola-draft", value); } catch {} };
  const send = async (retry?: Job) => {
    if (sending || active || (!retry && !draft.trim())) return;
    setSending(true); setError("");
    nonce.current ||= crypto.randomUUID();
    try {
      const response = await fetch("/api/schola/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(retry ? { action: "retry", jobId: retry.id, id: nonce.current } : { action: "send", message: draft.trim(), id: nonce.current }) });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Could not queue your message.");
      edit(""); await refresh();
      requestAnimationFrame(() => bottom.current?.scrollIntoView({ behavior: "instant", block: "end" }));
    } catch (err) { setError(err instanceof Error ? err.message : "Connection failed. Your draft is still here."); }
    finally { setSending(false); }
  };
  const workerOnline = !!data?.workerSeenAt && Date.now() - Date.parse(data.workerSeenAt) < 4 * 60000;
  const latestFailed = data?.jobs[0]?.status === "FAILED" ? data.jobs[0] : undefined;
  return <section className="schola-corner" aria-labelledby="schola-title"><header className="chat-heading"><div><span className="chat-glyph" aria-hidden="true">✳</span><div><h1 id="schola-title">Schola</h1><p>A place to think through your next step.</p></div></div><Badge tone={workerOnline ? "success" : "warning"}>{workerOnline ? "Ready here" : "Worker offline"}</Badge></header>
    <details className="connection-details"><summary><Icon name="shield" size={15} />{data?.settings.contextAllowed ? "Using your relevant project context" : "Fictional context only"}<Icon name="chevron" size={13} /></summary>{data ? <div><p><strong>Model:</strong> {data.settings.model}. {data.callsToday} / {data.settings.dailyCallLimit} calls today (UTC).</p><p><strong>Web search:</strong> {data.settings.searchProvider}. {data.search.message}</p><p>Known official pages can be read directly. Search results and model answers still need evidence. Your profile, budget, strategy and conversation may be sent through the configured model; credentials and private Calendar links are excluded.</p><p>Model and search settings live in <code>private/schola.local.json</code>. {data.settings.backgroundEnabled ? "New source changes can trigger a bounded review here." : "Background source review is off."} Schola’s tools read information; you make application and checklist changes.</p></div> : <p>Loading connection settings…</p>}</details>
    {offline && <p className="chat-notice" role="status">Connection interrupted. Your queued work continues on the homelab. Reconnecting…</p>}
    {!data && !error && <div className="chat-loading" aria-label="Loading conversation"><div className="skeleton" /><div className="skeleton" /></div>}
    {data && !data.messages.length && <div className="chat-welcome"><span aria-hidden="true">✳</span><h2>We can work it out, one question at a time.</h2><p>Ask about your plan, compare a few routes, or check what an official source actually says.</p><div className="chat-suggestions">{suggestions.map(s => <button key={s} onClick={() => { edit(s); input.current?.focus(); }}>{s}<Icon name="arrow" size={16} /></button>)}</div></div>}
    <div className="chat-messages" role="log" aria-label="Conversation with Schola" aria-live="polite" aria-relevant="additions">{data?.messages.map(message => <article key={message.id} className={`chat-message ${message.role}`}><header><strong>{message.role === "user" ? "You" : message.meta.kind === "source-review" ? "Schola · source review" : "Schola"}</strong><time dateTime={message.createdAt}>{dateTime(message.createdAt)}</time></header><MessageText text={message.content} />{!!message.meta.sources?.length && <details className="chat-sources"><summary>{message.meta.sources.length} source{message.meta.sources.length === 1 ? "" : "s"} consulted</summary>{message.meta.sources.map(source => <div key={source.url}><External href={source.url}>{new URL(source.url).hostname}</External><small>{source.kind} · {source.retrievedAt.slice(0, 10)}</small></div>)}</details>}</article>)}</div>
    {active && <div className="chat-working" role="status"><span className="status-dot running" /><div><strong>{active.status === "QUEUED" ? "Your message is saved in the queue." : "Schola is working through it."}</strong><p>{data?.tools.find(t => t.jobId === active.id)?.summary || "Gathering the context for a useful answer."} You can leave and come back.</p>{!workerOnline && <p>The assistant worker is offline. Your message will wait safely until it returns.</p>}</div></div>}
    {latestFailed && <div className="chat-notice"><p>{latestFailed.error}</p><button className="button secondary" disabled={sending || !!active} onClick={() => send(latestFailed)}><Icon name="refresh" size={15} />Retry saved message</button></div>}
    <div ref={bottom} className="chat-bottom" />
    {showNew && <button className="new-reply button secondary" onClick={() => { bottom.current?.scrollIntoView({ behavior: "instant" }); setShowNew(false); }}>Jump to new reply<Icon name="arrow" size={15} /></button>}
    <form className="chat-composer" onSubmit={e => { e.preventDefault(); send(); }}><label className="sr-only" htmlFor="schola-message">Message Schola</label><textarea ref={input} id="schola-message" placeholder="What’s on your mind?" rows={2} maxLength={6000} value={draft} onChange={e => edit(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} /><div><span>Saved here. Sent only when you tap Send.</span><button className="button primary" type="submit" disabled={sending || !!active || !draft.trim() || !data?.settings.configured}><span>{sending ? "Saving…" : "Send"}</span><Icon name="arrow" size={18} /></button></div>{error && <p role="alert" className="form-error">{error} <button type="button" className="text-button" onClick={() => refresh().then(() => setError("")).catch(e => setError(e.message))}>Reload</button></p>}</form>
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
