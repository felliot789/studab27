"use client";
import Link from "next/link";
import type { CalendarEvent, Dashboard } from "@/lib/schema";
import { dateConfidence, dateLabel, eventClock, eventDay, eventKind } from "@/lib/calendar";
import { Badge, Dialog, External, Icon } from "./ui";

export function EventRow({ event, data, onSelect }: { event: CalendarEvent; data: Dashboard; onSelect: (event: CalendarEvent) => void }) {
  const day = eventDay(event), route = data.routes.find(r => r.id === event.routeId)!;
  return <article className={`event-row ${day ? "" : "unconfirmed"}`}>
    <div className="event-date">{day ? <><strong>{dateLabel(day).split(" ")[0]}</strong><span>{dateLabel(day).split(" ")[1]}</span></> : <Icon name="clock" size={19} />}</div>
    <div className="event-copy"><span className="eyebrow">{eventKind(event)}{event.round ? ` · ${event.round}` : ""}</span><h3><button className="event-title" onClick={() => onSelect(event)}>{event.title}</button></h3><Link className="subtle-link" href={`/scholarships/${route.id}`}>{route.institution}</Link><small>{day ? event.endDate ? `Through ${dateLabel(event.endDate, true)} · ${eventClock(event)}` : eventClock(event) : dateConfidence(event)}</small></div>
    <button className="icon-button" aria-label={`View details for ${event.title}`} onClick={() => onSelect(event)}><Icon name="chevron" /></button>
  </article>;
}

export function EventDialog({ event, data, close }: { event: CalendarEvent; data: Dashboard; close: () => void }) {
  const day = eventDay(event), route = data.routes.find(r => r.id === event.routeId)!;
  const conditions = Array.isArray(event.conditions) ? event.conditions : event.conditions ? [event.conditions] : [];
  return <Dialog title="Calendar date" onClose={close}><section className="drawer-section event-dialog-intro"><Badge tone={day ? "success" : "warning"}>{dateConfidence(event)}</Badge><h2>{event.title}</h2><Link className="text-button" href={`/scholarships/${route.id}`}>{route.institution}<Icon name="arrow" size={15} /></Link><p className="event-date-large">{day ? `${dateLabel(day, true)}${event.endDate ? ` – ${dateLabel(event.endDate, true)}` : ""}` : "No confirmed calendar date"}</p><p>{day ? eventClock(event) : "This item is kept off the calendar until the target-cycle date is established."}</p>{event.deadlineAtWib && <p className="fine-print">Published: {event.date} at {event.time} {event.timezone}. Calendar displays the converted time in Jakarta (WIB).</p>}{day && !event.deadlineAtWib && <p className="fine-print">Shown on the publisher’s calendar date. A date without a confirmed time zone cannot be converted to a precise WIB cutoff.</p>}{!day && event.candidateDate && <p className="planning-note">Reference only: {dateLabel(event.candidateDate, true)}. This is an unconfirmed candidate date; it is not a deadline.</p>}</section>
    <section className="drawer-section"><h3>Which application?</h3><dl className="reference-list"><div><dt>Cycle</dt><dd>{event.cycle}</dd></div><div><dt>Program</dt><dd>{event.program}</dd></div>{event.round && <div><dt>Round</dt><dd>{event.round}</dd></div>}</dl>{conditions.map(c => <p className="planning-note" key={c}>{c}</p>)}{event.prerequisiteEventIds.length > 0 && <><h4>Before this step</h4><ul>{event.prerequisiteEventIds.map(id => <li key={id}>{data.calendarEvents.find(e => e.id === id)?.title || "Confirm the prerequisite in the official call"}</li>)}</ul></>}</section>
    <section className="drawer-section"><h3>What the source supports</h3><p>{event.sourceEvidence}</p><p>{event.sourceReview.note}</p><External href={event.sourceUrl}>Read official source</External>{event.sourceReview.evidence.filter(e => e.url !== event.sourceUrl).map(e => <External href={e.url} key={e.url}>Supporting official source</External>)}<p className="fine-print">Source review: {event.checkedAt}. Dates are research evidence, not a personal eligibility check. Recheck the linked call before applying.</p></section>
  </Dialog>;
}
