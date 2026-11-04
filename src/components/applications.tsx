"use client";
import Link from "next/link";
import { useState } from "react";
import { APPLICATION_STATUSES, label } from "@/lib/schema";
import { activeApplication, dateLabel, eventDay, upcomingEvents } from "@/lib/calendar";
import { Badge, CountryLabel, Icon, PageHeading, type ViewProps } from "./ui";

export default function Applications({ data, act, busy }: ViewProps) {
  const [filter, setFilter] = useState("active");
  const active = data.overlays.filter(activeApplication), dropped = data.overlays.filter(o => o.applicationStatus === "DROP");
  const routes = data.routes.filter(r => {
    const o = data.overlays.find(o => o.routeId === r.id)!;
    return filter === "dropped" ? o.applicationStatus === "DROP" : filter === "active" ? activeApplication(o) : o.applicationStatus === filter;
  });
  const next = upcomingEvents(data.calendarEvents, data.overlays);
  return <><PageHeading title="Your applications" extra={<Link className="button secondary" href="/scholarships"><Icon name="plus" size={16} />Find a scholarship</Link>}>Track application status, pending checks, and deadlines.</PageHeading><div className="application-context"><Icon name="compass" size={21} /><p>Saving keeps a scholarship on your shortlist. Set its application status when you decide to pursue it.</p></div><div className="text-tabs application-tabs" role="group" aria-label="Application status"><button aria-pressed={filter === "active"} onClick={() => setFilter("active")}>All active <span>{active.length}</span></button>{(["RESEARCHING", "IN_PROGRESS", "SUBMITTED"] as const).map(s => <button key={s} aria-pressed={filter === s} onClick={() => setFilter(s)}>{label(s)} <span>{data.overlays.filter(o => o.applicationStatus === s).length}</span></button>)}{!!dropped.length && <button aria-pressed={filter === "dropped"} onClick={() => setFilter("dropped")}>Set aside <span>{dropped.length}</span></button>}</div>
    <div className="application-list">{routes.map(r => {
      const o = data.overlays.find(o => o.routeId === r.id)!, e = data.evaluations.find(e => e.routeId === r.id)!, upcoming = next.find(n => n.routeId === r.id), checksLeft = [e.curriculum, e.graduation, e.budget].filter(g => g.status === "UNKNOWN").length;
      return <article className="application-row" key={r.id}><div><span className="eyebrow"><CountryLabel country={r.country} /></span><h2><Link href={`/scholarships/${r.id}`}>{r.institution}<Icon name="arrow" size={17} /></Link></h2><p>{r.scholarshipName}</p><div className="application-followup"><Icon name="calendar" size={15} /><span>{upcoming ? `${dateLabel(eventDay(upcoming)!, true)} · ${upcoming.title}` : "Next deadline still to confirm"}</span></div><Link className="text-button" href={`/scholarships/${r.id}?tab=plan`}>{checksLeft ? `${checksLeft} planning check${checksLeft === 1 ? "" : "s"} to complete` : "Review your plan"}<Icon name="chevron" size={13} /></Link>{e.overall === "BLOCKED" && <Badge tone="warning">Review a blocking check</Badge>}</div><label>Progress<select aria-label={`Application status for ${r.institution}`} disabled={busy} value={o.applicationStatus} onChange={event => act({ action: "overlay", id: r.id, patch: { applicationStatus: event.target.value } }, "Application progress updated.")}>{APPLICATION_STATUSES.map(s => <option key={s} value={s}>{s === "DROP" ? "Set aside" : label(s)}</option>)}</select></label></article>;
    })}</div>{!routes.length && <div className="empty-state"><Icon name="applications" size={32} /><h2>{filter === "active" ? "No active applications" : "No applications at this stage"}</h2><p>Open a scholarship and set its application status in the Your plan tab.</p><Link className="button primary" href="/scholarships">Browse scholarships<Icon name="arrow" size={16} /></Link></div>}
  </>;
}
