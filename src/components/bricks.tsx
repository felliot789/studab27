"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { checklistProgress, trackedRoutes } from "@/lib/tracker";
import ApplicationChecklist from "./application-checklist";
import { PageHeading, CountryFlag, Icon, type ViewProps } from "./ui";

export default function Bricks({ data, act, busy }: ViewProps) {
  const tab = useSearchParams().get("tab") === "reusable" ? "reusable" : "scholarships";
  const routes = trackedRoutes(data.routes, data.overlays);
  const total = data.bricks.reduce((n, b) => n + b.items.length, 0);
  const done = Object.values(data.state.bricks).filter(Boolean).length;
  return <><PageHeading title="Documents">Prepare what each scholarship asks for. Reuse a base document where it fits.</PageHeading>
    <div className="text-tabs document-tabs" role="group" aria-label="Document views">{[{ id: "scholarships", title: "By scholarship" }, { id: "reusable", title: "Reusable documents" }].map(item => <button key={item.id} aria-pressed={tab === item.id} onClick={() => { window.history.replaceState(null, "", `/documents${item.id === "reusable" ? "?tab=reusable" : ""}`); }}>{item.title}</button>)}</div>
    <section hidden={tab !== "scholarships"}>
      <p className="intro-note">Document steps from tracked checklists. Updates also appear in the scholarship checklist. Files are stored separately; this page records readiness.</p>
      <div className="document-scholarships">{routes.map(route => {
        const progress = checklistProgress(route, data.state, true);
        return <details className="document-scholarship" key={route.id}><summary><span><strong><CountryFlag country={route.country} labelled />{route.institution}</strong><small>{route.scholarshipName}</small></span><span>{progress.total ? `${progress.done} / ${progress.total} ready` : "Guide to research"}</span></summary><div className="document-scholarship-body"><Link className="text-button" href={`/scholarships/${route.id}`}>Full application checklist<Icon name="arrow" size={16} /></Link><ApplicationChecklist route={route} documentsOnly data={data} act={act} busy={busy} /></div></details>;
      })}</div>
      {!routes.length && <div className="empty-state"><h2>Add a scholarship first</h2><p>Document requirements appear here for tracked scholarships. Reusable document packs are also available.</p><Link href="/scholarships?browse=1" className="button primary">Add scholarship</Link></div>}
    </section>
    <section hidden={tab !== "reusable"}>
    <p className="readiness-total">{done} of {total} reusable steps ready</p>
    <p className="intro-note">Mark a step ready when the document is available or the action is complete. This checklist records readiness; files are stored separately.</p>
    <div className="brick-list">{data.bricks.map(brick => {
      const complete = brick.items.filter(i => data.state.bricks[`${brick.id}:${i.id}`]).length;
      return <section className="brick" id={brick.id} key={brick.id}><div className="brick-overview"><Icon name="layers" size={24} /><h2>{brick.title}</h2><p>{brick.description}</p><code>{brick.folder}</code><div className="progress-track" role="progressbar" aria-label={`${brick.title} readiness`} aria-valuenow={complete} aria-valuemin={0} aria-valuemax={brick.items.length}><span style={{ width: `${complete / brick.items.length * 100}%` }} /></div><small>{complete} of {brick.items.length} steps</small></div><div className="brick-checklist">{brick.items.map(item => { const key = `${brick.id}:${item.id}`, checked = !!data.state.bricks[key]; return <label className={`checklist-item ${checked ? "done" : ""}`} key={item.id}><input type="checkbox" checked={checked} disabled={busy} onChange={e => act({ action: "brick", key, done: e.target.checked }, e.target.checked ? "Document step marked ready." : "Document step reopened.")} /><span>{item.label}</span>{checked && <Icon name="check" size={15} />}</label>; })}</div></section>;
    })}</div><p className="end-note">Keep submitted versions frozen. Check each scholarship's requested version before marking its own step ready.</p>
    </section>
  </>;
}
