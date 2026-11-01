"use client";
import { useEffect, useRef, useState } from "react";
import { gapText, label, type Evaluation } from "@/lib/schema";
import { Badge, dateTime, External, Icon, PageHeading, type ViewProps } from "./ui";

export default function Watchtower({ data, act, busy, openRoute }: ViewProps) {
  const [sat, setSat] = useState(Math.min(1560, Math.max(1350, data.profile.snapshot.satPlan?.targetTotal || 1480)));
  const [cap, setCap] = useState(data.profile.snapshot.maxFamilyContributionIdrMPerMonth);
  const [sim, setSim] = useState<Evaluation[] | null>(null);
  const [simError, setSimError] = useState("");
  const [calculating, setCalculating] = useState(true);
  const [capture, setCapture] = useState("");
  const [filter, setFilter] = useState("CHANGED");
  const [simFilter, setSimFilter] = useState("changed");
  const generation = useRef(0);
  useEffect(() => {
    const version = ++generation.current;
    const controller = new AbortController();
    setCalculating(true); setSimError("");
    const timer = setTimeout(async () => {
      try {
        const res = await fetch("/api/schola", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "simulate", sat, cap }), signal: controller.signal });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || "Could not calculate scenario.");
        if (version === generation.current) setSim(result.evaluations);
      } catch (error) { if (!controller.signal.aborted && version === generation.current) { setSim(null); setSimError(error instanceof Error ? error.message : "Scenario unavailable."); } }
      finally { if (version === generation.current) setCalculating(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [sat, cap, data.overlays]);
  const base = new Map(data.evaluations.map(e => [e.routeId, e]));
  const changed = sim?.filter(e => e.budget.status !== base.get(e.routeId)?.budget.status) || [];
  const selected = simFilter === "changed" ? changed : sim || [];
  const events = data.watch.events.filter(e => filter === "ALL" || e.kind === filter).sort((a,b) => b.at.localeCompare(a.at));
  const successful = Object.values(data.watch.sources).filter(s => s.status === "OK").length;
  const failed = Object.entries(data.watch.sources).filter(([, s]) => s.status === "ERROR");
  const staleRun = data.watch.running && Date.now() - Date.parse(data.watch.runStartedAt || "") > 30 * 60 * 1000;
  const running = data.watch.running && !staleRun;
  return <><PageHeading title="Stay curious. Stay grounded." extra={<button className="button secondary" disabled={busy || !!running} onClick={() => act({ action: "scan" }, "Scan started. Source results will appear as they finish.")}><Icon name="refresh" />{running ? "Scanning sources…" : "Check sources now"}</button>}>Official-source observations and what-if scenarios, with their limits in view.</PageHeading>
    <section className="watch-status"><div><span className={`status-dot ${running ? "running" : ""}`} /><strong>{running ? "Source scan in progress" : staleRun ? "Previous scan did not finish" : data.watch.lastRunAt ? "Last scan completed" : "No source scan yet"}</strong><span>{running && data.watch.progress ? `${data.watch.progress.checked} / ${data.watch.progress.total} sources` : data.watch.lastRunAt ? dateTime(data.watch.lastRunAt) : "Run a scan to establish the first baseline."}</span></div><p>{data.schedule.label} · {successful} successful snapshots{failed.length ? ` · ${failed.length} fetch errors` : ""}</p>{data.schedule.nextRunAt && <p>Next scheduled run: {data.schedule.nextRunAt}</p>}<p className="fine-print">A text change is a prompt to review the source. It does not automatically verify a rule, update a deadline, or notify an admissions office.</p></section>
    <section className="simulator" aria-labelledby="sim-heading"><div className="section-line"><h2 id="sim-heading">What if your plan changes?</h2><Badge>Scenario only</Badge></div><p>Try a SAT target and family budget. Your saved profile stays unchanged.</p><div className="sim-controls"><label htmlFor="sat-scenario">SAT scenario<strong>{sat}</strong><input id="sat-scenario" type="range" min="1350" max="1560" step="10" value={sat} onChange={e => setSat(Number(e.target.value))} /><span className="range-labels"><span>1350</span><span>1560</span></span></label><label htmlFor="budget-scenario">Monthly family cap<strong>IDR {cap}M</strong><input id="budget-scenario" type="range" min="0" max="15" step="0.5" value={cap} onChange={e => setCap(Number(e.target.value))} /><span className="range-labels"><span>IDR 0M</span><span>IDR 15M</span></span></label></div>
      <div className="scenario-reading" role="status" aria-live="polite">{calculating ? "Recalculating your scenario…" : simError ? simError : <><strong>{sim?.filter(e => e.budget.status === "PASS").length} budget estimates fit this cap.</strong><span>{sim?.filter(e => e.sat.status === "TARGET_MET").length} advisory SAT targets met. {sim?.filter(e => e.overall === "NEEDS_VERIFICATION").length} routes still need rule verification.</span></>}</div><p className="fine-print">SAT benchmarks are planning targets, not admission or scholarship cutoffs. Unknown costs and unverified curriculum or graduation rules do not unlock a route.</p>
      <div className="section-line"><h3>Route impact</h3><label className="compact-label"><span className="sr-only">Scenario routes</span><select value={simFilter} onChange={e => setSimFilter(e.target.value)}><option value="changed">Budget status changed ({changed.length})</option><option value="all">All {data.routes.length} routes</option></select></label></div>
      {!calculating && !simError && !selected.length && <p className="empty-inline">No budget gate changed at this cap. Choose “All routes” to inspect the scenario.</p>}
      {!simError && <div className="scenario-list" aria-busy={calculating}>{selected.map(e => <div className="scenario-row" key={e.routeId}><button className="route-name" onClick={() => openRoute(e.routeId)}>{data.routes.find(r => r.id === e.routeId)?.institution}</button><span>{gapText(e)}</span><Badge tone={e.budget.status === "PASS" ? "success" : e.budget.status === "FAIL" ? "danger" : "warning"}>{e.budget.status === "PASS" ? "Estimate fits" : e.budget.status === "FAIL" ? "Over cap" : "Uncertain"}</Badge><small>{e.sat.target ? `SAT ${e.sat.target}+ advisory · ${e.sat.status === "TARGET_MET" ? "scenario meets target" : "below target"}` : "SAT target not quantified"}</small></div>)}</div>}
    </section>
    <div className="watch-columns"><section className="source-feed"><div className="section-line"><h2>Source observations</h2><label><span className="sr-only">Filter source observations</span><select value={filter} onChange={e => setFilter(e.target.value)}><option value="CHANGED">Changes</option><option value="ERROR">Fetch errors</option><option value="BASELINE">First baselines</option><option value="ALL">All observations</option></select></label></div>{events.slice(0, 40).map(event => <article className="feed-item" key={event.id}><div className="section-line"><Badge tone={event.kind === "ERROR" ? "danger" : event.kind === "CHANGED" ? "warning" : "neutral"}>{label(event.kind)}</Badge><small>{dateTime(event.at)}</small></div><h3>{event.routeIds.length ? data.routes.find(r => r.id === event.routeIds[0])?.institution || "Official source" : "Official source"}</h3><p>{event.summary}</p><External href={event.url}>Inspect source</External>{event.excerpt && <details><summary>View normalized text diff</summary><pre>{event.excerpt}</pre></details>}</article>)}{!events.length && <div className="empty-state compact"><Icon name="radar" size={27} /><h3>{filter === "CHANGED" ? "No text changes recorded." : "No observations in this view."}</h3><p>{data.watch.lastRunAt ? "First snapshots establish a baseline. Only later successful fetches can show changes." : "Start with a source scan. An empty feed does not establish that scholarship pages are unchanged."}</p></div>}{events.length > 40 && <p className="fine-print">Showing the 40 latest matching observations. Full bounded history is in the local watchtower JSON.</p>}
      {!!failed.length && <details className="failed-sources"><summary>{failed.length} sources need attention</summary>{failed.map(([url, source]) => <div key={url}><External href={url}>{new URL(url).hostname}</External><p>{source.error}</p><small>Last good snapshot: {source.lastSuccessAt ? dateTime(source.lastSuccessAt) : "none"}</small></div>)}</details>}
    </section><aside className="capture-column"><section className="inbox-capture"><h2>Leave it in the inbox.</h2><p>A link, a question, a scholarship rumor. Capture it now; decide later.</p><form onSubmit={async e => { e.preventDefault(); if (await act({ action: "inbox", text: capture }, "Captured in your local inbox.")) setCapture(""); }}><label className="sr-only" htmlFor="capture-note">Link or note</label><textarea id="capture-note" placeholder="Paste a link or write a note…" value={capture} onChange={e => setCapture(e.target.value)} maxLength={4000} rows={4} required /><button className="button secondary" type="submit" disabled={busy || !capture.trim()}><Icon name="plus" size={15} />Save to inbox</button></form><small>Stored locally in 07_Inbox. Links are not fetched automatically.</small></section><section className="inbox-list"><h3>Your captures</h3>{!data.inbox.length && <p className="muted">Nothing waiting here. A little room for the next discovery.</p>}{data.inbox.slice(0, 30).map(item => <article key={item.id} className={item.status === "TRIAGED" ? "triaged" : ""}><p>{item.text}</p><div className="section-line"><small>{dateTime(item.createdAt)}</small><button className="text-button" disabled={busy} onClick={() => act({ action: "triage", id: item.id, status: item.status === "NEW" ? "TRIAGED" : "NEW" }, item.status === "NEW" ? "Capture marked triaged." : "Capture reopened.")}>{item.status === "NEW" ? "Mark triaged" : "Reopen"}</button></div></article>)}</section></aside></div>
  </>;
}
