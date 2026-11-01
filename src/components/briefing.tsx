"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { ViewProps } from "./ui";
import { Badge, External, Icon, shortDate } from "./ui";

type Focus = { taskId: string; remaining: number; endAt: number | null };
const focusKey = "studab27:focus:v1";

export default function Briefing({ data, act, busy, openRoute }: ViewProps) {
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
    if (await act({ action: "task", id, command }, command === "done" ? "Step completed. One less thing to carry." : command === "snooze" ? "Snoozed for 24 hours." : "Another step is ready.")) {
      if (focus?.taskId === id) { setFocus(null); setSeconds(900); }
    }
  };
  const now = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });
  const horizon = data.sourceNotes.filter(n => (n.deadlineAt || n.deadlineDate || "").slice(0, 10) >= now).sort((a, b) => (a.deadlineAt || a.deadlineDate || "").localeCompare(b.deadlineAt || b.deadlineDate || "")).slice(0, 3);
  const completed = Object.values(data.state.tasks).filter(t => t.status === "DONE").length;
  const localUpcoming = data.milestones.filter(m => m.date >= now && !/UBC/i.test(m.title)).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 2);
  return <>
    <header className="briefing-welcome"><div className="schola-glyph" aria-hidden="true">✳</div><p>A little progress goes a long way.</p><h1>Let’s take the next step.</h1><p className="welcome-note">You don’t need to solve all 57 routes today.<br />Pick one small thing. Give it fifteen minutes.</p></header>
    <div className="briefing-layout"><section aria-labelledby="next-move"><div className="section-line"><h2 id="next-move">Your next moves</h2><span>{data.briefing.cards.length} small steps</span></div>
      <div className="task-list">{data.briefing.cards.map((task, index) => <article className={`task ${index === 0 ? "featured" : ""}`} key={task.id}>
        <div className="task-meta"><span className="task-category"><Icon name={task.category === "DECISION_GATE" ? "compass" : task.category === "VERIFY_RULE" ? "search" : "layers"} size={15} />{task.category === "DECISION_GATE" ? "A decision to make" : task.category === "VERIFY_RULE" ? "A rule to verify" : "A document step"}</span><span><Icon name="clock" size={14} />{task.minutes} min</span></div>
        <h3>{task.title}</h3><p>{task.description}</p>
        <details className="task-details" open={index === 0}><summary>Make it manageable</summary><ol>{task.steps.map(step => <li key={step}>{step}</li>)}</ol>{task.sources?.slice(0, 2).map((source, i) => <External key={source} href={source}>Official source{i ? ` ${i + 1}` : ""}</External>)}</details>
        {!!task.routeIds.length && <div className="task-route-links">{task.routeIds.slice(0, 3).map(id => <button key={id} className="text-button" onClick={() => openRoute(id)}>{data.routes.find(r => r.id === id)?.institution}<Icon name="chevron" size={13} /></button>)}</div>}
        <div className="task-actions"><button className={index === 0 ? "button primary" : "button secondary"} disabled={busy} onClick={() => { setFocus({ taskId: task.id, remaining: 900, endAt: Date.now() + 900000 }); setSeconds(900); }}><Icon name="play" size={14} />{focus?.taskId === task.id && seconds > 0 ? "Restart focus" : "Start 15-min focus"}</button><button className="button quiet" disabled={busy} onClick={() => changeTask(task.id, "done")}><Icon name="check" size={16} />Mark done</button><details className="task-menu"><summary aria-label={`More options for ${task.title}`}>···</summary><div><button disabled={busy} onClick={() => changeTask(task.id, "snooze")}>Snooze 24 hours</button><button disabled={busy} onClick={() => changeTask(task.id, "replace")}>Replace card</button></div></details></div>
      </article>)}</div>
      {!data.briefing.cards.length && <div className="empty-state"><Icon name="check" size={30} /><h3>You’ve made room to breathe.</h3><p>There are no unsnoozed steps left. Check your documents or return to a completed step when you need to.</p><Link href="/bricks" className="button secondary">Open document readiness</Link></div>}
      {!!completed && <details className="completed-tasks"><summary>{completed} completed step{completed === 1 ? "" : "s"}</summary>{Object.entries(data.state.tasks).filter(([, s]) => s.status === "DONE").map(([id]) => <div key={id}><span>{data.briefing.taskTitles[id] || id.replaceAll("-", " ")}</span><button className="text-button" disabled={busy} onClick={() => act({ action: "task", id, command: "undo" }, "Step returned to the queue.")}>Return to queue</button></div>)}</details>}
    </section>
    <aside className="briefing-aside">
      <section className={`focus-panel ${focus ? "active" : ""}`} aria-labelledby="focus-heading"><div className="section-line"><h2 id="focus-heading">A moment to focus</h2><Icon name="moon" size={17} /></div><div className="timer" aria-label={`${Math.floor(seconds / 60)} minutes ${seconds % 60} seconds remaining`}>{String(Math.floor(seconds / 60)).padStart(2, "0")}<span>:</span>{String(seconds % 60).padStart(2, "0")}</div><p>{focus ? seconds === 0 ? "Your focus block is complete. Mark the task done when you’re ready." : "One task. Everything else can wait." : "Choose a next move to start your focus block."}</p>{focus && <div className="timer-actions"><button className="button secondary" onClick={() => { const paused = !!focus.endAt; setFocus({ ...focus, remaining: seconds, endAt: paused ? null : Date.now() + seconds * 1000 }); }} disabled={seconds === 0}><Icon name={focus.endAt ? "pause" : "play"} size={14} />{focus.endAt ? "Pause" : "Resume"}</button><button className="button quiet" onClick={() => { setFocus(null); setSeconds(900); }}>Reset</button></div>}</section>
      <section className="horizon" aria-labelledby="horizon-heading"><h2 id="horizon-heading">On the horizon</h2>{horizon.map(note => <div className="horizon-item" key={note.id}><div className="date-tile"><strong>{shortDate(note.deadlineAt || note.deadlineDate!).split(" ")[0]}</strong><span>{shortDate(note.deadlineAt || note.deadlineDate!).split(" ")[1]}</span></div><div><External href={note.sourceUrl}>{note.deadlineLabel}</External><small>{note.deadlineAt ? new Date(note.deadlineAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" }) + " WIB" : "Confirm cutoff time & zone"}</small></div></div>)}{!!localUpcoming.length && <details className="milestone-list"><summary>Your saved milestones</summary>{localUpcoming.map(m => <div key={m.title}><small>{shortDate(m.date)} · personal target</small><p>{m.title}</p>{m.calendarUrl && <External href={m.calendarUrl}>View Calendar record</External>}</div>)}<p className="fine-print">Imported records; Calendar sync is not connected. Official source corrections take precedence.</p></details>}</section>
      <section className="compass-note"><Icon name="compass" size={22} /><h2>Keep your compass.</h2><p>Funding first. A sustainable path.<br />Prestige can be the tiebreaker.</p><span>Family cap: IDR {data.profile.snapshot.maxFamilyContributionIdrMPerMonth}M / month</span><Link href="/catalogue">Explore the catalogue <Icon name="arrow" size={15} /></Link></section>
    </aside></div>
    {focus && <div className="focus-dock"><div><strong role="timer">{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</strong><span>{seconds === 0 ? "Focus complete" : focus.endAt ? "One thing at a time" : "Focus paused"}</span></div><button className="button secondary" disabled={seconds === 0} onClick={() => setFocus({ ...focus, remaining: seconds, endAt: focus.endAt ? null : Date.now() + seconds * 1000 })}><Icon name={focus.endAt ? "pause" : "play"} size={16} />{focus.endAt ? "Pause" : "Resume"}</button><button className="icon-button" aria-label="End focus block" onClick={() => { setFocus(null); setSeconds(900); }}><Icon name="close" size={18} /></button></div>}
    <p className="end-note">Small steps count. You can leave the rest for tomorrow.</p>
  </>;
}
