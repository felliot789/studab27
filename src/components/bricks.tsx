"use client";
import { PageHeading, Icon, type ViewProps } from "./ui";

export default function Bricks({ data, act, busy }: ViewProps) {
  const total = data.bricks.reduce((n, b) => n + b.items.length, 0);
  const done = Object.values(data.state.bricks).filter(Boolean).length;
  return <><PageHeading title="Build once. Reuse often." extra={<span className="readiness-total">{done} of {total} steps ready</span>}>Four document packs that make the next application easier.</PageHeading>
    <p className="intro-note">Check a step only when you have the document or have completed the action. This checklist stores readiness; your actual documents stay in your own folders.</p>
    <div className="brick-list">{data.bricks.map(brick => {
      const complete = brick.items.filter(i => data.state.bricks[`${brick.id}:${i.id}`]).length;
      return <section className="brick" id={brick.id} key={brick.id}><div className="brick-overview"><Icon name="layers" size={24} /><h2>{brick.title}</h2><p>{brick.description}</p><code>{brick.folder}</code><div className="progress-track" role="progressbar" aria-label={`${brick.title} readiness`} aria-valuenow={complete} aria-valuemin={0} aria-valuemax={brick.items.length}><span style={{ width: `${complete / brick.items.length * 100}%` }} /></div><small>{complete} of {brick.items.length} steps</small></div><div className="brick-checklist">{brick.items.map(item => { const key = `${brick.id}:${item.id}`, checked = !!data.state.bricks[key]; return <label className={`checklist-item ${checked ? "done" : ""}`} key={item.id}><input type="checkbox" checked={checked} disabled={busy} onChange={e => act({ action: "brick", key, done: e.target.checked }, e.target.checked ? "Document step marked ready." : "Document step reopened.")} /><span>{item.label}</span>{checked && <Icon name="check" size={15} />}</label>; })}</div></section>;
    })}</div><p className="end-note">Keep submitted versions frozen. Use a new working copy for later edits.</p>
  </>;
}
