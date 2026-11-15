"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { DraftFields, ScholarshipDraft } from "@/lib/scholarship-drafts";
import { Badge, dateTime, Dialog, External, Icon } from "./ui";

const endpoint = "/api/schola/scholarships";
const leadKey = "studab27:scholarship-lead";
const statusLabels = { RESEARCHING: "Researching", READY: "Ready to review", FAILED: "Needs attention", ACCEPTED: "Added to Explore" };
const knownText = (value: string, fallback: string) => value.trim() && value.trim().toUpperCase() !== "UNKNOWN" ? value : fallback;
const detailFields: { key: Exclude<keyof DraftFields, "country" | "institution" | "scholarshipName" | "officialSourceUrl" | "unresolvedQuestions">; label: string }[] = [
  { key: "programAndLanguageNotes", label: "Undergraduate subjects and teaching language" },
  { key: "indonesianApplicantNotes", label: "Indonesian applicant requirements" },
  { key: "languageOrTestNotes", label: "Language and test requirements" },
  { key: "separateScholarshipApp", label: "Separate scholarship application" },
  { key: "preGradApplyAllowed", label: "Applying before graduation" },
  { key: "renewalAndBondTerms", label: "Renewal and return obligations" },
  { key: "publicRiskOrCaveat", label: "Evidence limits and caveats" },
];

async function request(payload?: Record<string, unknown>) {
  const response = await fetch(endpoint, payload ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : { cache: "no-store" });
  if (response.status === 401) { window.location.assign("/login"); throw new Error("Sign in to continue. Draft retained."); }
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "The scholarship draft could not be saved. Changes retained.");
  return value;
}

export default function ScholarshipDraftsButton() {
  const [open, setOpen] = useState(false);
  return <><button type="button" className="button secondary" aria-haspopup="dialog" onClick={() => setOpen(true)}><Icon name="plus" size={16} />Add new scholarship</button>{open && <Dialog title="Scholarship drafts" className="scholarship-drafts-dialog" onClose={() => setOpen(false)}><ScholarshipDrafts /></Dialog>}</>;
}

function ScholarshipDrafts() {
  const [drafts, setDrafts] = useState<ScholarshipDraft[]>([]);
  const [mode, setMode] = useState<"PRIVATE" | "DEMO" | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const leadId = useRef<string | null>(null);
  const queryId = useId(), sourceId = useId();
  const refresh = useCallback(async () => {
    const value = await request();
    setDrafts(value.drafts); setMode(value.mode);
  }, []);
  const researching = drafts.some(draft => draft.status === "RESEARCHING");
  useEffect(() => {
    try { const lead = JSON.parse(sessionStorage.getItem(leadKey) || "null"); if (lead) { setQuery(typeof lead.query === "string" ? lead.query : ""); setSourceUrl(typeof lead.sourceUrl === "string" ? lead.sourceUrl : ""); leadId.current = typeof lead.id === "string" ? lead.id : null; } } catch { /* Browser storage is optional. */ }
    refresh().catch(err => setError(err.message));
  }, [refresh]);
  useEffect(() => {
    const tick = () => { if (!document.hidden) refresh().catch(() => setError("Connection interrupted. Saved drafts remain available. Reload to reconnect.")); };
    const timer = setInterval(tick, researching ? 3000 : 20000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
  }, [refresh, researching]);
  const editLead = (nextQuery: string, nextSource: string) => {
    setQuery(nextQuery); setSourceUrl(nextSource); leadId.current = null;
    try { sessionStorage.setItem(leadKey, JSON.stringify({ query: nextQuery, sourceUrl: nextSource })); } catch { /* Browser storage is optional. */ }
  };
  const start = async () => {
    if (busy || mode !== "PRIVATE" || !query.trim()) return;
    setBusy(true); setError("");
    leadId.current ||= crypto.randomUUID();
    try { sessionStorage.setItem(leadKey, JSON.stringify({ query, sourceUrl, id: leadId.current })); } catch { /* Browser storage is optional. */ }
    try {
      const value = await request({ action: "start", id: leadId.current, query: query.trim(), ...(sourceUrl.trim() ? { sourceUrl: sourceUrl.trim() } : {}) });
      setSelectedId(value.draft?.id || leadId.current);
      editLead("", "");
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not start research. Lead retained."); await refresh().catch(() => {}); }
    finally { setBusy(false); }
  };
  const selected = drafts.find(draft => draft.id === selectedId);
  return <div className="scholarship-drafts">
    <section className="drawer-section draft-intro"><p>Schola researches official sources and saves a draft for review. Adding a draft creates a local Explore entry; tracking and priorities remain separate actions.</p><p className="fine-print">Drafts and accepted entries are included in workspace exports. Research continues after this dialog closes.</p></section>
    {mode === "DEMO" && <p className="chat-notice" role="status">Scholarship additions are available in a private workspace. The demo catalogue remains unchanged.</p>}
    {error && <p className="form-error draft-error" role="alert">{error} <button type="button" className="text-button" onClick={() => refresh().then(() => setError("")).catch(err => setError(err.message))}>Reload drafts</button></p>}
    {mode === null && !error && <div className="chat-loading" aria-label="Loading scholarship drafts"><div className="skeleton" /><div className="skeleton" /></div>}
    {selected ? <DraftEditor key={selected.id} draft={selected} disabled={mode !== "PRIVATE"} refresh={refresh} back={() => setSelectedId(null)} /> : <>
      <form className="drawer-section stacked-form draft-lead" onSubmit={event => { event.preventDefault(); start(); }}>
        <h3>Research a scholarship</h3>
        <label htmlFor={queryId}>Scholarship name or research question<textarea id={queryId} value={query} onChange={event => editLead(event.target.value, sourceUrl)} required maxLength={1000} rows={2} placeholder="Scholarship name, institution, and country" disabled={busy || mode !== "PRIVATE"} /></label>
        <label htmlFor={sourceId}>Official source URL <span className="field-optional">(optional)</span><input id={sourceId} type="url" inputMode="url" value={sourceUrl} onChange={event => editLead(query, event.target.value)} maxLength={2048} placeholder="https://…" disabled={busy || mode !== "PRIVATE"} /></label>
        <p className="fine-print">Use public scholarship information only. Eligibility, funding and dates stay unresolved until supported by evidence.</p>
        <button className="button primary" type="submit" disabled={busy || mode !== "PRIVATE" || !query.trim()}>{busy ? "Saving request…" : "Research and save draft"}<Icon name="arrow" size={16} /></button>
      </form>
      <section className="drawer-section draft-list" aria-labelledby="saved-drafts-heading"><h3 id="saved-drafts-heading">Saved drafts{drafts.length ? ` · ${drafts.length}` : ""}</h3>{!drafts.length && mode && <p>No drafts yet. A scholarship name or official link starts the research.</p>}{drafts.map(draft => <button type="button" key={draft.id} className="draft-list-item" onClick={() => setSelectedId(draft.id)}><span><strong>{knownText(draft.fields.scholarshipName, draft.query)}</strong><small>{knownText(draft.fields.institution, "Institution to confirm")}</small><small>{dateTime(draft.updatedAt)}</small></span><span><Badge tone={draft.status === "FAILED" ? "warning" : draft.status === "ACCEPTED" ? "success" : "neutral"}>{statusLabels[draft.status]}</Badge><Icon name="chevron" size={16} /></span></button>)}</section>
    </>}
  </div>;
}

function DraftEditor({ draft, disabled, refresh, back }: { draft: ScholarshipDraft; disabled: boolean; refresh: () => Promise<void>; back: () => void }) {
  const router = useRouter();
  const storageKey = `studab27:scholarship-edit:${draft.id}`;
  const [editing, setEditing] = useState(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      const validFields = saved?.fields && Object.keys(draft.fields).every(key => key === "unresolvedQuestions" ? Array.isArray(saved.fields[key]) && saved.fields[key].every((item: unknown) => typeof item === "string") : typeof saved.fields[key] === "string");
      if (validFields && Number.isInteger(saved.revision) && draft.status !== "ACCEPTED") return { fields: saved.fields as DraftFields, revision: saved.revision as number, dirty: true };
    } catch { /* Browser storage is optional. */ }
    return { fields: draft.fields, revision: draft.revision, dirty: false };
  });
  const { fields, revision, dirty } = editing;
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [acceptedRouteId, setAcceptedRouteId] = useState(draft.acceptedRouteId);
  const [existingRouteId, setExistingRouteId] = useState<string | null>(null);
  const processing = draft.status === "RESEARCHING";
  const accepted = draft.status === "ACCEPTED" || !!acceptedRouteId;
  useEffect(() => {
    setEditing(current => current.dirty ? current : { fields: draft.fields, revision: draft.revision, dirty: false });
  }, [draft.fields, draft.revision]);
  const edit = (key: keyof DraftFields, value: string | string[]) => {
    const next = { ...fields, [key]: value };
    setEditing({ fields: next, revision, dirty: true }); setNotice(""); setExistingRouteId(null);
    try { sessionStorage.setItem(storageKey, JSON.stringify({ revision, fields: next })); } catch { /* Browser storage is optional. */ }
  };
  const loadSaved = () => {
    setEditing({ fields: draft.fields, revision: draft.revision, dirty: false }); setError(""); setNotice("Saved version loaded."); setExistingRouteId(null);
    try { sessionStorage.removeItem(storageKey); } catch { /* Browser storage is optional. */ }
  };
  const act = async (action: "save" | "accept" | "retry") => {
    if (busy || disabled) return;
    const submittedFields = { ...fields, unresolvedQuestions: fields.unresolvedQuestions.map(question => question.trim()).filter(Boolean) };
    if (action !== "retry" && submittedFields.unresolvedQuestions.length > 30) { setError("Keep up to 30 unresolved questions. Edits are retained."); return; }
    if (action !== "retry" && submittedFields.unresolvedQuestions.some(question => question.length > 1000)) { setError("Each unresolved question must be 1,000 characters or fewer. Edits are retained."); return; }
    setBusy(action); setError(""); setNotice("");
    try {
      const value = await request({ action, id: draft.id, revision, ...(action === "retry" ? {} : { fields: submittedFields }) });
      if (value.duplicate) setExistingRouteId(value.routeId);
      else {
        setEditing({ fields: value.draft?.fields || submittedFields, revision: value.draft?.revision ?? revision, dirty: false });
        if (value.routeId || value.draft?.acceptedRouteId) setAcceptedRouteId(value.routeId || value.draft.acceptedRouteId);
        try { sessionStorage.removeItem(storageKey); } catch { /* Browser storage is optional. */ }
      }
      setNotice(action === "save" ? "Draft saved." : action === "retry" ? "Research queued. The saved draft remains available." : value.duplicate ? "This scholarship already exists in Explore." : "Scholarship added to Explore.");
      if (action === "accept") router.refresh();
      await refresh().catch(() => setError("The change was saved, but the draft list could not refresh. Reopen drafts to reconnect."));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save this change. Edits retained."); }
    finally { setBusy(""); }
  };
  return <section className="draft-editor">
    <button type="button" className="text-button draft-back" onClick={back}><Icon name="back" size={15} />All drafts</button>
    <header className="draft-editor-heading"><h3>{knownText(draft.fields.scholarshipName, draft.query)}</h3><Badge tone={accepted ? "success" : draft.status === "FAILED" ? "warning" : "neutral"}>{accepted ? "Added to Explore" : existingRouteId ? "Existing entry found" : statusLabels[draft.status]}</Badge><p>Saved {dateTime(draft.updatedAt)}</p></header>
    {processing && <p className="chat-notice" role="status">Research is in progress. This draft remains saved after the dialog closes.</p>}
    {draft.error && !accepted && <p className="chat-notice">{draft.error} Partial findings remain available for editing.</p>}
    {!!draft.matches.length && <section className="draft-matches" aria-label="Possible existing scholarships"><h4>Check existing entries</h4><p>An existing scholarship may cover the same award.</p>{draft.matches.map(match => <Link key={match.routeId} href={`/scholarships/${match.routeId}?tab=overview`}>{match.institution} · {match.scholarshipName}<small>{match.kind === "EXACT" ? "Matching entry" : "Possible match"}</small><Icon name="arrow" size={15} /></Link>)}</section>}
    {error && <p className="form-error draft-error" role="alert">{error}</p>}
    {existingRouteId && <div className="draft-matches"><p role="status">This scholarship already exists in Explore. No new entry was added; draft edits remain available.</p><a href={`/scholarships/${existingRouteId}?tab=overview`}>Open existing scholarship<Icon name="arrow" size={15} /></a></div>}
    {accepted ? <div className="draft-accepted"><p role="status">{notice || "This draft has been added to the local catalogue."}</p><a className="button primary" href={`/scholarships/${acceptedRouteId || draft.acceptedRouteId}?tab=overview`}>Open scholarship<Icon name="arrow" size={16} /></a><p className="fine-print">Tracking and priorities can be set from the scholarship page.</p></div> : <form className="stacked-form draft-fields" onSubmit={event => { event.preventDefault(); act("save"); }}>
      <fieldset disabled={disabled || processing || !!busy}><legend>Scholarship details</legend><div className="draft-identity-grid">{([{ key: "scholarshipName", label: "Scholarship name", maxLength: 300 }, { key: "institution", label: "Institution or sponsor", maxLength: 300 }, { key: "country", label: "Country", maxLength: 100 }] as const).map(field => <label key={field.key}>{field.label}<input value={fields[field.key]} maxLength={field.maxLength} onChange={event => edit(field.key, event.target.value)} /></label>)}</div>
        <label>Official source URL<input type="url" inputMode="url" value={fields.officialSourceUrl} maxLength={2048} onChange={event => edit("officialSourceUrl", event.target.value)} /></label>
        <label className="draft-funding">Funding and living costs<textarea value={fields.benefitsCoverage} rows={3} maxLength={4000} onChange={event => edit("benefitsCoverage", event.target.value)} /></label>
        <details className="draft-more"><summary>Funding, requirements and unresolved questions</summary><div>{detailFields.map(field => <label key={field.key}>{field.label}<textarea value={fields[field.key]} rows={3} maxLength={4000} onChange={event => edit(field.key, event.target.value)} /></label>)}<label>Unresolved questions <span className="field-optional">(one per line; up to 30, 1,000 characters each)</span><textarea value={fields.unresolvedQuestions.join("\n")} rows={3} maxLength={30029} onChange={event => edit("unresolvedQuestions", event.target.value.split("\n"))} /></label></div></details>
      </fieldset>
      <p className="fine-print">Missing evidence may remain UNKNOWN. Save edited failed drafts before adding. Adding an entry does not verify eligibility or create confirmed calendar dates.</p>
      {dirty && <p className="draft-unsaved" role="status">Unsaved edits retained in this browser tab. <button type="button" className="text-button" onClick={loadSaved} disabled={!!busy}>Load saved version</button></p>}
      {dirty && revision !== draft.revision && <p className="chat-notice" role="status">The saved draft changed. Local edits are retained; load the saved version before saving again.</p>}
      {notice && !existingRouteId && <p className="draft-notice" role="status">{notice}</p>}
      <div className="draft-actions"><button type="submit" className="button secondary" disabled={disabled || processing || !!busy || (dirty && revision !== draft.revision)}>{busy === "save" ? "Saving…" : "Save draft"}</button><button type="button" className="button primary" disabled={disabled || draft.status !== "READY" || !!busy || !fields.officialSourceUrl.trim() || [fields.scholarshipName, fields.institution, fields.country].some(value => !value.trim() || value.trim().toUpperCase() === "UNKNOWN") || (dirty && revision !== draft.revision)} onClick={() => act("accept")}>{busy === "accept" ? "Adding…" : "Add to Explore"}<Icon name="plus" size={16} /></button>{draft.status === "FAILED" && <button type="button" className="text-button" disabled={disabled || !!busy || dirty} onClick={() => act("retry")}>{busy === "retry" ? "Queuing…" : "Retry research"}<Icon name="refresh" size={15} /></button>}</div>
    </form>}
    <section className="draft-sources"><h4>Research sources · {draft.sources.length}</h4><p>Source findings are research evidence and still need review.</p>{!draft.sources.length && <p>No source findings saved yet.</p>}{draft.sources.map((source, index) => <article key={`${source.url}:${index}`}><External href={source.url}>{source.title || source.url}</External>{source.finding && <p>{source.finding}</p>}<small>{source.checkedAt ? `Checked ${dateTime(source.checkedAt)}` : "Check date unknown"}</small></article>)}</section>
  </section>;
}
