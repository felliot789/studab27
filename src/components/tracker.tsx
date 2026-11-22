"use client";
import Link from "next/link";
import { APPLICATION_STATUSES, label, type Overlay } from "@/lib/schema";
import { dateLabel, eventDay, upcomingEvents } from "@/lib/calendar";
import { checklistProgress, PURSUIT_HELP, PURSUIT_LABELS, pursuitLevel, trackedRoutes, type PursuitGroup } from "@/lib/tracker";
import { Badge, CountryLabel, Icon, PageHeading, type Action, type ViewProps } from "./ui";
import { ScholaFindingBanner } from "./schola-sessions";

export function PursuitControls({ overlay, act, busy }: { overlay: Overlay; act: Action; busy: boolean }) {
  return <div className="pursuit-controls">
    <label>Priority<select aria-label="Pursuit priority" value={overlay.pursuitLevel || ""} disabled={busy} onChange={e => act({ action: "overlay", id: overlay.routeId, patch: { pursuitLevel: e.target.value || null } }, "Priority saved.")}>
      <option value="">Decide later</option>{(["FOCUS", "SECONDARY", "BACKUP"] as const).map(level => <option key={level} value={level}>{PURSUIT_LABELS[level]}</option>)}
    </select></label>
    <label>Application progress<select aria-label="Application progress" value={overlay.applicationStatus} disabled={busy} onChange={e => act({ action: "overlay", id: overlay.routeId, patch: { applicationStatus: e.target.value } }, "Application progress saved.")}>
      {APPLICATION_STATUSES.map(status => <option key={status} value={status}>{status === "IN_PROGRESS" ? "Preparing" : status === "DROP" ? "Not pursuing" : label(status)}</option>)}
    </select></label>
  </div>;
}

export default function Tracker({ data, act, busy }: ViewProps) {
  const routes = trackedRoutes(data.routes, data.overlays);
  const upcoming = upcomingEvents(data.calendarEvents, data.overlays);
  return <>
    <PageHeading title="Scholarship tracker" extra={<Link className="button secondary" href="/scholarships?browse=1"><Icon name="plus" size={17} />Add scholarship</Link>}>Application checklists, progress, and deadlines.</PageHeading>
    <ScholaFindingBanner />
    {!!routes.length && <p className="tracker-intro">{routes.length} scholarship{routes.length === 1 ? "" : "s"} tracked.</p>}
    {(["FOCUS", "SECONDARY", "BACKUP", "UNSET"] as PursuitGroup[]).map(group => {
      const members = routes.filter(route => pursuitLevel(data.overlays.find(o => o.routeId === route.id)!) === group);
      if (!members.length) return null;
      return <section className="tracker-group" key={group} aria-labelledby={`priority-${group}`}>
        <header className="tracker-group-heading"><h2 id={`priority-${group}`}>{PURSUIT_LABELS[group]} <span className="count-pill">{members.length}</span></h2><p>{PURSUIT_HELP[group]}</p></header>
        {members.map(route => {
          const overlay = data.overlays.find(o => o.routeId === route.id)!, progress = checklistProgress(route, data.state);
          const nextDate = upcoming.find(event => event.routeId === route.id);
          return <article className={`tracker-row ${overlay.mainTarget ? "main-target" : ""}`} key={route.id} aria-label={route.institution}>
            <div className="tracker-identity"><div className="tracker-country"><CountryLabel country={route.country} />{overlay.mainTarget && <Badge tone="success">Main target</Badge>}</div><h3><Link href={`/scholarships/${route.id}`}>{route.institution}</Link></h3><p>{route.scholarshipName}</p>
              <div className="tracker-progress"><span>{progress.total ? `${progress.done} of ${progress.total} steps done` : "Checklist to research"}</span>{progress.total > 0 && <div className="progress-track" role="progressbar" aria-label={`${route.institution} checklist`} aria-valuenow={progress.done} aria-valuemin={0} aria-valuemax={progress.total}><span style={{ width: `${progress.done / progress.total * 100}%` }} /></div>}</div>
              <p className="tracker-next"><span>Next step</span>{progress.next?.title || (progress.total ? "Checklist complete. Check the application portal for updates." : "Review the official programme requirements.")}</p>
              <p className="tracker-date"><Icon name="calendar" size={15} />{nextDate ? `${dateLabel(eventDay(nextDate)!, true)} · ${nextDate.title}` : "2027 dates still to confirm"}</p>
            </div>
            <div className="tracker-actions"><PursuitControls overlay={overlay} act={act} busy={busy} /><div className="tracker-page-links"><Link className="text-button" href={`/scholarships/${route.id}?tab=overview`}>Read description</Link><Link className={`button ${overlay.mainTarget ? "primary" : "secondary"}`} href={`/scholarships/${route.id}`}>Open checklist<Icon name="arrow" size={16} /></Link></div></div>
          </article>;
        })}
      </section>;
    })}
    {!routes.length && <div className="empty-state"><Icon name="bookmark" size={30} /><h2>No tracked scholarships</h2><p>Add a scholarship to track its checklist, documents, and dates.</p><Link className="button primary" href="/scholarships?browse=1">Choose a scholarship<Icon name="arrow" size={16} /></Link></div>}
    <details className="tracker-help"><summary>How priorities work</summary><dl>{(["FOCUS", "SECONDARY", "BACKUP", "UNSET"] as PursuitGroup[]).map(group => <div key={group}><dt>{PURSUIT_LABELS[group]}</dt><dd>{PURSUIT_HELP[group]}</dd></div>)}</dl><p>Priority sets an application’s focus level. Application progress records its current stage. Changing either preserves checklist progress and notes.</p></details>
  </>;
}
