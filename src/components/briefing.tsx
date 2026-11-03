"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { ViewProps } from "./ui";
import type { CalendarEvent } from "@/lib/schema";
import { upcomingEvents } from "@/lib/calendar";
import { EventDialog, EventRow } from "./calendar-event";
import { External, Icon } from "./ui";

type Focus = { taskId: string; remaining: number; endAt: number | null };
const focusKey = "studab27:focus:v1";

export default function Briefing({ data, act, busy, openRoute }: ViewProps) {
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [seconds, setSeconds] = useState(900);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try { const saved = JSON.parse(sessionStorage.getItem(focusKey) || "null"); if (saved && typeof saved.taskId === "string" && typeof saved.remaining === "number" && (saved.endAt === null || typeof saved.endAt === "number")) { setFocus(saved); setSeconds(saved.endAt ? Math.max(0, Math.ceil((saved.endAt - Date.now()) / 1000)) : saved.remaining); } } catch { /* Focus history is optional. */ }
    setReady(true);
  }, []);
  useEffect(() => { if (ready) sessionStorage.setItem(focusKey, JSON.stringify(focus)); }, [focus, ready]);
  useEffect(() => {
    if (!focus?.endAt) return;
    const tick = () => setSeconds(Math.max(0, Math.ceil((focus.endAt! - Date.now()) / 1000)));
    tick(); const id = window.setInterval(tick, 1000); return () => clearInterval(id);
  }, [focus]);
  const changeTask = async (id: string, command: string) => {
    if (await act({ action: "task", id, command }, command === "done" ? "Task completed." : command === "snooze" ? "Snoozed for 24 hours." : "Task replaced.")) {
      if (focus?.taskId === id) { setFocus(null); setSeconds(900); }
    }
  };
  const horizon = upcomingEvents(data.calendarEvents, data.overlays).slice(0, 3);
  const completed = Object.values(data.state.tasks).filter(t => t.status === "DONE").length;
  const readyDocuments = data.bricks.reduce((n, b) => n + b.items.filter(i => data.state.bricks[`${b.id}:${i.id}`]).length, 0);
  const totalDocuments = data.bricks.reduce((n, b) => n + b.items.length, 0);
  return <>
    <header className="briefing-welcome"><p className="eyebrow">2027 applications</p><h1>Today</h1><p className="welcome-note">Priority tasks, calendar dates, and document readiness.</p></header>
    <div className="briefing-layout"><section aria-labelledby="next-move"><div className="section-line"><h2 id="next-move">Priority tasks</h2><span>{data.briefing.cards.length} tasks</span></div>
      <div className="task-list">{data.briefing.cards.map((task, index) => <article className={`task ${index === 0 ? "featured" : ""}`} key={task.id}>
        <div className="task-meta"><span className="task-category"><Icon name={task.category === "DECISION_GATE" ? "compass" : task.category === "VERIFY_RULE" ? "search" : "layers"} size={15} />{task.category === "DECISION_GATE" ? "Decision" : task.category === "VERIFY_RULE" ? "Rule verification" : "Documents"}</span><span><Icon name="clock" size={14} />{task.minutes} min</span></div>
        <h3>{task.title}</h3><p>{task.description}</p>
        <details className="task-details" open={index === 0}><summary>Task instructions</summary><ol>{task.steps.map(step => <li key={step}>{step}</li>)}</ol>{task.sources?.slice(0, 2).map((source, i) => <External key={source} href={source}>Official source{i ? ` ${i + 1}` : ""}</External>)}</details>
        {!!task.routeIds.length && <div className="task-route-links">{task.routeIds.slice(0, 3).map(id => <button key={id} className="text-button" onClick={() => openRoute(id)}>{data.routes.find(r => r.id === id)?.institution}<Icon name="chevron" size={13} /></button>)}</div>}
        <div className="task-actions"><button className={index === 0 ? "button primary" : "button secondary"} disabled={busy} onClick={() => { setFocus({ taskId: task.id, remaining: 900, endAt: Date.now() + 900000 }); setSeconds(900); }}><Icon name="play" size={14} />{focus?.taskId === task.id && seconds > 0 ? "Restart timer" : "Start 15-min timer"}</button><button className="button quiet" disabled={busy} onClick={() => changeTask(task.id, "done")}><Icon name="check" size={16} />Mark done</button><details className="task-menu"><summary aria-label={`More options for ${task.title}`}>···</summary><div><button disabled={busy} onClick={() => changeTask(task.id, "snooze")}>Snooze 24 hours</button><button disabled={busy} onClick={() => changeTask(task.id, "replace")}>Replace task</button></div></details></div>
      </article>)}</div>
      {!data.briefing.cards.length && <div className="empty-state"><Icon name="check" size={30} /><h3>No pending tasks</h3><p>No tasks are currently pending. Review documents or reopen a completed task.</p><Link href="/documents" className="button secondary">Open document readiness</Link></div>}
      {!!completed && <details className="completed-tasks"><summary>{completed} completed step{completed === 1 ? "" : "s"}</summary>{Object.entries(data.state.tasks).filter(([, s]) => s.status === "DONE").map(([id]) => <div key={id}><span>{data.briefing.taskTitles[id] || id.replaceAll("-", " ")}</span><button className="text-button" disabled={busy} onClick={() => act({ action: "task", id, command: "undo" }, "Step returned to the queue.")}>Return to queue</button></div>)}</details>}
    </section>
    <aside className="briefing-aside">
      {focus && <section className={`focus-panel ${focus ? "active" : ""}`} aria-labelledby="focus-heading"><div className="section-line"><h2 id="focus-heading">Focus timer</h2><Icon name="moon" size={17} /></div><div className="timer" aria-label={`${Math.floor(seconds / 60)} minutes ${seconds % 60} seconds remaining`}>{String(Math.floor(seconds / 60)).padStart(2, "0")}<span>:</span>{String(seconds % 60).padStart(2, "0")}</div><p>{seconds === 0 ? "Timer complete. Mark the task done when the work is finished." : focus.endAt ? "Timer running." : "Timer paused."}</p>{focus && <div className="timer-actions"><button className="button secondary" onClick={() => { const paused = !!focus.endAt; setFocus({ ...focus, remaining: seconds, endAt: paused ? null : Date.now() + seconds * 1000 }); }} disabled={seconds === 0}><Icon name={focus.endAt ? "pause" : "play"} size={14} />{focus.endAt ? "Pause" : "Resume"}</button><button className="button quiet" onClick={() => { setFocus(null); setSeconds(900); }}>Reset</button></div>}</section>}

      <section className="horizon" aria-labelledby="horizon-heading"><div className="section-line"><h2 id="horizon-heading">Upcoming dates</h2><Link className="text-button" href="/calendar">Calendar<Icon name="arrow" size={14} /></Link></div><p className="aside-caption">Saved scholarships & active applications</p>{horizon.map(event => <EventRow key={event.id} event={event} data={data} onSelect={setSelected} />)}{!horizon.length && <p className="quiet-empty">No upcoming published dates in your shortlist. <Link className="text-button" href="/calendar">Open calendar</Link></p>}</section>
      <section className="document-shortcut"><Icon name="layers" size={23} /><h2>Document readiness</h2><p>Track reusable documents and application preparation requirements.</p><span>{readyDocuments} of {totalDocuments} steps ready</span><Link className="text-button" href="/documents">Open your documents<Icon name="arrow" size={15} /></Link></section>
    </aside></div>
    {focus && <div className="focus-dock"><div><strong role="timer">{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</strong><span>{seconds === 0 ? "Timer complete" : focus.endAt ? "Timer running" : "Timer paused"}</span></div><button className="button secondary" disabled={seconds === 0} onClick={() => setFocus({ ...focus, remaining: seconds, endAt: focus.endAt ? null : Date.now() + seconds * 1000 })}><Icon name={focus.endAt ? "pause" : "play"} size={16} />{focus.endAt ? "Pause" : "Resume"}</button><button className="icon-button" aria-label="Stop timer" onClick={() => { setFocus(null); setSeconds(900); }}><Icon name="close" size={18} /></button></div>}
    {selected && <EventDialog event={selected} data={data} close={() => setSelected(null)} />}
  </>;
}
