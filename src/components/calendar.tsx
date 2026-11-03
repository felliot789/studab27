"use client";
import Link from "next/link";
import { useState } from "react";
import type { CalendarEvent } from "@/lib/schema";
import { dateLabel, eventDay, eventEndDay, eventKind, inMyCalendar, todayWib } from "@/lib/calendar";
import { EventDialog, EventRow } from "./calendar-event";
import { Icon, PageHeading, type ViewProps } from "./ui";

export default function Calendar({ data, initialRouteId }: ViewProps & { initialRouteId?: string }) {
  const today = todayWib();
  const focusedRoute = data.routes.some(r => r.id === initialRouteId) ? initialRouteId : undefined;
  const [scope, setScope] = useState(focusedRoute ? "all" : "saved"), [month, setMonth] = useState(today.slice(0, 7));
  const [view, setView] = useState("month"), [routeFilter, setRouteFilter] = useState(focusedRoute || "all"), [kind, setKind] = useState("all");
  const [selectedDay, setSelectedDay] = useState<string | null>(null), [selected, setSelected] = useState<CalendarEvent | null>(null);
  const myIds = new Set(data.overlays.filter(inMyCalendar).map(o => o.routeId));
  const routes = data.routes.filter(r => scope === "all" || myIds.has(r.id));
  const scoped = data.calendarEvents.filter(e => (scope === "all" || myIds.has(e.routeId)) && (routeFilter === "all" || e.routeId === routeFilter) && (kind === "all" || eventKind(e) === kind));
  const dated = scoped.filter(e => eventDay(e)).sort((a, b) => eventDay(a)!.localeCompare(eventDay(b)!) || a.id.localeCompare(b.id));
  const unconfirmed = scoped.filter(e => !eventDay(e));
  const monthStart = new Date(month + "-01T12:00:00Z"), year = monthStart.getUTCFullYear(), monthIndex = monthStart.getUTCMonth();
  const days = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate(), offset = (monthStart.getUTCDay() + 6) % 7;
  const personal = routeFilter === "all" && kind === "all" ? data.milestones : [];
  const inMonth = dated.filter(e => eventDay(e)! <= `${month}-${days}` && eventEndDay(e)! >= `${month}-01`);
  const visible = selectedDay ? inMonth.filter(e => eventDay(e)! <= selectedDay && eventEndDay(e)! >= selectedDay) : inMonth;
  const localVisible = personal.filter(m => selectedDay ? m.date === selectedDay : m.date.startsWith(month));
  const moveMonth = (amount: number) => {
    const date = new Date(Date.UTC(year, monthIndex + amount, 1));
    setMonth(date.toISOString().slice(0, 7)); setSelectedDay(null);
  };
  return <><PageHeading title="Your calendar">Application openings, deadlines, and the steps in between.</PageHeading>
    <div className="calendar-intro"><div className="segmented" role="group" aria-label="Calendar routes"><button aria-pressed={scope === "saved"} onClick={() => { setScope("saved"); setRouteFilter("all"); setSelectedDay(null); }}>Saved & active <span>{myIds.size}</span></button><button aria-pressed={scope === "all"} onClick={() => { setScope("all"); setRouteFilter("all"); setSelectedDay(null); }}>All routes <span>{data.routes.length}</span></button></div><p>{scope === "saved" ? "Your saved scholarships and ongoing applications." : "Explore dates across the full scholarship catalogue."}</p></div>
    <div className="calendar-toolbar"><div className="month-navigation"><button className="icon-button" aria-label="Previous month" onClick={() => moveMonth(-1)}><Icon name="back" /></button><h2 aria-live="polite">{monthStart.toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" })}</h2><button className="icon-button" aria-label="Next month" onClick={() => moveMonth(1)}><Icon name="chevron" /></button><button className="button quiet" onClick={() => { setMonth(today.slice(0, 7)); setSelectedDay(null); }}>Today</button></div><div className="segmented compact" role="group" aria-label="Calendar view"><button aria-pressed={view === "month"} onClick={() => setView("month")}>Month</button><button aria-pressed={view === "agenda"} onClick={() => setView("agenda")}>Agenda</button></div></div>
    <div className="calendar-filters"><label>Scholarship<select value={routeFilter} onChange={e => { setRouteFilter(e.target.value); setSelectedDay(null); }}><option value="all">All {scope === "saved" ? "saved & active" : "57"} routes</option>{routes.map(r => <option key={r.id} value={r.id}>{r.institution} · {r.scholarshipName}</option>)}</select></label><label>Step<select value={kind} onChange={e => { setKind(e.target.value); setSelectedDay(null); }}><option value="all">All steps</option>{[...new Set(data.calendarEvents.map(eventKind))].sort().map(k => <option key={k}>{k}</option>)}</select></label><span className="calendar-zone"><Icon name="clock" size={15} />Times in WIB · Jakarta</span></div>
    {scope === "saved" && !myIds.size && <div className="empty-state calendar-empty"><Icon name="calendar" size={30} /><h2>No saved or active routes</h2><p>Save a scholarship or start an application to include its dates here. Select All routes to view the full catalogue.</p><div className="inline-actions"><Link className="button primary" href="/scholarships">Find scholarships<Icon name="arrow" size={15} /></Link><button className="button secondary" onClick={() => setScope("all")}>Show all routes</button></div></div>}
    {view === "month" && <section className="calendar-month" aria-label={`${monthStart.toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" })} calendar`}><div className="calendar-weekdays">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <span key={d}>{d}</span>)}</div><div className="calendar-grid">{Array.from({ length: Math.ceil((offset + days) / 7) * 7 }, (_, i) => {
      const n = i - offset + 1;
      if (n < 1 || n > days) return <div className="calendar-cell outside" key={i} />;
      const date = `${month}-${String(n).padStart(2, "0")}`, events = inMonth.filter(e => eventDay(e)! <= date && eventEndDay(e)! >= date), targets = personal.filter(m => m.date === date);
      return <button key={i} className={`calendar-cell ${date === today ? "today" : ""} ${selectedDay === date ? "selected" : ""}`} aria-pressed={selectedDay === date} aria-label={`${dateLabel(date, true)}, ${events.length} scholarship events, ${targets.length} personal targets${date === today ? ", today" : ""}`} onClick={() => { setSelectedDay(selectedDay === date ? null : date); }}><span className="day-number">{n}</span><span className="day-events">{events.slice(0, 2).map(e => <span className="day-event" key={e.id} title={e.title}><i />{data.routes.find(r => r.id === e.routeId)?.institution}</span>)}{!!targets.length && <span className="day-event personal"><i />Personal target</span>}{events.length > 2 && <span className="more-events">+{events.length - 2} more</span>}</span><span className="mobile-event-dots" aria-hidden="true">{events.slice(0, 3).map(e => <i key={e.id} />)}{!!targets.length && <i className="personal" />}</span></button>;
    })}</div></section>}
    {view === "month" && <p className="calendar-hint">Choose a day to see its dates below.</p>}
    <section className="calendar-agenda" aria-labelledby="agenda-heading"><div className="section-line"><h2 id="agenda-heading">{selectedDay ? dateLabel(selectedDay, true) : "This month"}</h2>{selectedDay ? <button className="text-button" onClick={() => setSelectedDay(null)}>Show whole month</button> : <span>{inMonth.length} published date{inMonth.length === 1 ? "" : "s"}</span>}</div><div aria-live="polite">{visible.map(e => <EventRow key={e.id} event={e} data={data} onSelect={setSelected} />)}{localVisible.map((m, i) => <article className="event-row personal-target" key={`${m.title}-${i}`}><div className="event-date"><strong>{dateLabel(m.date).split(" ")[0]}</strong><span>{dateLabel(m.date).split(" ")[1]}</span></div><div className="event-copy"><span className="eyebrow">Personal / imported target</span><h3>{m.title}</h3><small>{m.timeWIB ? `${m.timeWIB} WIB · ` : ""}Your planning record; check published dates separately.</small>{m.notes && <p>{m.notes}</p>}</div></article>)}{!visible.length && !localVisible.length && <p className="quiet-empty">No published dates {selectedDay ? "on this day" : "this month"} for these routes. Dates still awaiting confirmation are below.</p>}</div></section>
    <details className="dates-pending"><summary><span><Icon name="clock" size={18} />Dates to confirm <span className="count-pill">{unconfirmed.length}</span></span><Icon name="chevron" size={16} /></summary><p>Annual rules, conflicting sources, and unpublished dates stay here. They are not placed on calendar days.</p>{unconfirmed.map(e => <EventRow key={e.id} event={e} data={data} onSelect={setSelected} />)}{!unconfirmed.length && <p className="quiet-empty">No unconfirmed dates in this selection.</p>}</details>
    <p className="end-note">Date-only entries use the publisher’s calendar day. Published times are converted to WIB only when the time zone is known. Source review: 3 November 2026.</p>
    {selected && <EventDialog event={selected} data={data} close={() => setSelected(null)} />}
  </>;
}
