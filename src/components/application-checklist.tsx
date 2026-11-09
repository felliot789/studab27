"use client";
import Link from "next/link";
import { useState } from "react";
import type { ApplicationGuide, ApplicationRequirement, RequirementProgress, Route } from "@/lib/schema";
import { BASIS_LABELS, checklistProgress, REQUIREMENT_LABELS } from "@/lib/tracker";
import { Badge, External, Icon, type ViewProps } from "./ui";

export default function ApplicationChecklist({ route, documentsOnly = false, data, act, busy }: Pick<ViewProps, "data" | "act" | "busy"> & { route: Route; documentsOnly?: boolean }) {
  const guide = route.applicationGuide, progress = checklistProgress(route, data.state, documentsOnly);
  if (!guide) return <div className="quiet-empty"><h2>Build this scholarship's checklist</h2><p>A programme-specific guide has not been researched yet. Start with the official call and ask Schola to identify the requirements and missing evidence.</p><External href={route.officialSourceUrl}>Open the official scholarship page</External><Link className="text-button" href="/schola">Ask Schola<Icon name="arrow" size={16} /></Link></div>;
  return <div className="application-checklist">
    <div className="checklist-intro"><p>{guide.summary}</p><div className="checklist-meta"><span>{progress.done} of {progress.total} {documentsOnly ? "document steps" : "steps"} done{progress.skipped > 0 ? ` · ${progress.skipped} not needed` : ""}</span><span>Sources reviewed {guide.reviewedAt}</span></div><p className="fine-print">Preparation progress is saved separately for this scholarship. Recheck marked steps against the new call before relying on them.</p></div>
    {guide.sections.map(section => {
      const items = section.items.filter(item => !documentsOnly || item.kind === "DOCUMENT");
      if (!items.length) return null;
      return <section className="checklist-section" key={section.id} aria-label={section.title}><h3>{section.title}</h3>{items.map(item => <RequirementRow key={item.id} item={item} guide={guide} routeId={route.id} progress={data.state.requirements?.[route.id]?.[item.id]} sharedReady={!!item.sharedKey && !!data.state.bricks[item.sharedKey]} initiallyOpen={item.id === progress.next?.id} act={act} busy={busy} />)}</section>;
    })}
    {!progress.total && <p className="quiet-empty">No applicable {documentsOnly ? "document " : ""}steps in this guide.</p>}
  </div>;
}

function RequirementRow({ item, guide, routeId, progress, sharedReady, initiallyOpen, act, busy }: { item: ApplicationRequirement; guide: ApplicationGuide; routeId: string; progress?: RequirementProgress; sharedReady: boolean; initiallyOpen: boolean } & Pick<ViewProps, "act" | "busy">) {
  const [note, setNote] = useState(progress?.note || "");
  const [open, setOpen] = useState(initiallyOpen);
  const needsRecheck = progress?.status === "NOT_NEEDED" && !item.optional;
  const status = needsRecheck ? "TODO" : progress?.status || "TODO";
  return <details className={`requirement-row ${status === "DONE" ? "done" : ""}`} open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary><span className="requirement-title">{status === "DONE" && <Icon name="check" size={17} />}<span>{item.title}<small>{BASIS_LABELS[item.basis]}{item.optional ? " · if applicable" : ""}</small></span></span><Badge tone={status === "DONE" ? "success" : "neutral"}>{needsRecheck ? "Recheck progress" : REQUIREMENT_LABELS[status]}</Badge></summary>
    <div className="requirement-body"><p>{item.detail}</p>{needsRecheck && <p className="fine-print">An earlier checklist marked this step not needed. The current guide lists it as required. The earlier record is preserved; check the current call and choose its progress.</p>}
      {item.sharedKey && <p className="shared-document">{sharedReady ? "The reusable document step is ready. Check this scholarship's version, translation, and format before marking this step done." : "The base document can be prepared in the reusable pack."} <Link href={`/documents?tab=reusable#${item.sharedKey.split(":")[0]}`}>Open reusable pack<Icon name="arrow" size={14} /></Link></p>}
      <label className="requirement-status">Step progress<select aria-label={`Progress: ${item.title}`} value={status} disabled={busy} onChange={event => act({ action: "requirement", routeId, id: item.id, status: event.target.value }, "Checklist progress saved.")}>{Object.entries(REQUIREMENT_LABELS).filter(([key]) => key !== "NOT_NEEDED" || item.optional).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>
      <div className="requirement-sources">{item.sourceIds.map(id => {
        const source = guide.sources.find(source => source.id === id)!;
        return <div key={id}><External href={source.url}>{source.title}</External><small>{source.scope}</small></div>;
      })}</div>
      <form className="requirement-note" onSubmit={async event => { event.preventDefault(); await act({ action: "requirement", routeId, id: item.id, note }, "Checklist note saved."); }}><label>Private note<textarea aria-label={`Note: ${item.title}`} value={note} onChange={event => setNote(event.target.value)} rows={2} maxLength={2000} placeholder="Readiness, missing items, or file location" /></label><button className="button secondary" disabled={busy || note === (progress?.note || "")}>Save note</button></form>
    </div>
  </details>;
}
