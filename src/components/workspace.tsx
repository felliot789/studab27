"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { Dashboard } from "@/lib/schema";
import Briefing from "./briefing";
import Catalogue, { RouteDrawer } from "./catalogue";
import Bricks from "./bricks";
import Watchtower from "./watchtower";
import { Badge, Dialog, External, Icon, type Action } from "./ui";

type View = "briefing" | "catalogue" | "bricks" | "watchtower";
const nav: { id: View; href: string; title: string; icon: string }[] = [
  { id: "briefing", href: "/", title: "Today’s briefing", icon: "home" },
  { id: "catalogue", href: "/catalogue", title: "Scholarship catalogue", icon: "compass" },
  { id: "bricks", href: "/bricks", title: "Document readiness", icon: "layers" },
  { id: "watchtower", href: "/watchtower", title: "Watchtower & simulator", icon: "radar" },
];

export default function Workspace({ initial, view }: { initial: Dashboard; view: View }) {
  const [data, setData] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [routeId, setRouteId] = useState<string | null>(null);
  const [vaultOpen, setVaultOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(null);
  useEffect(() => { setData(initial); }, [initial]);
  const refresh = useCallback(async () => {
    const response = await fetch("/api/schola", { cache: "no-store" });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Could not reload local state.");
    setData(value);
  }, []);
  useEffect(() => {
    if (view !== "watchtower" && !data.watch.running) return;
    const timer = setInterval(() => refresh().catch(() => setToast({ text: "Could not refresh source status. Displayed observations may be stale.", error: true })), 15000);
    return () => clearInterval(timer);
  }, [view, data.watch.running, refresh]);
  useEffect(() => { if (toast && !toast.error) { const timer = setTimeout(() => setToast(null), 5500); return () => clearTimeout(timer); } }, [toast]);
  const act: Action = async (payload, message) => {
    if (busy) return false;
    setBusy(true);
    try {
      const response = await fetch("/api/schola", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "This change could not be saved.");
      await refresh();
      if (message) setToast({ text: message, error: false });
      return true;
    } catch (error) { setToast({ text: error instanceof Error ? error.message : "Change failed. Try again.", error: true }); return false; }
    finally { setBusy(false); }
  };
  const props = { data, act, busy, openRoute: setRouteId };
  const route = data.routes.find(r => r.id === routeId);
  const title = nav.find(n => n.id === view)!.title;
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to content</a><aside className="sidebar"><Link href="/" className="brand" aria-label="StudAb27 home"><span className="brand-mark">S<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 10 10 2M3 2h7v7" /></svg></span><span>StudAb<span className="brand-year">27</span></span></Link><span className="sidebar-subtitle">Your next step abroad.</span><nav aria-label="Main navigation">{nav.map(item => <Link key={item.id} href={item.href} className={view === item.id ? "nav-link active" : "nav-link"} aria-current={view === item.id ? "page" : undefined}><Icon name={item.icon} size={19} /><span>{item.title}</span>{item.id === "catalogue" && <small>{data.routes.length}</small>}</Link>)}</nav><div className="sidebar-bottom"><div className="schola-status"><span className={`status-dot ${data.watch.running ? "running" : ""}`} /><div><strong>Schola</strong><small>{data.watch.running ? "Checking official sources" : data.schedule.active ? "12-hour checks scheduled" : "Ready when you are"}</small></div></div><button className="vault-button" onClick={() => setVaultOpen(true)}><span className="vault-avatar"><Icon name="shield" size={19} /></span><span><strong>{data.mode === "PRIVATE" ? "Private workspace" : "Demo workspace"}</strong><small>{data.mode === "PRIVATE" ? "Your vault · this device" : "Fictional sample profile"}</small></span><Icon name="chevron" size={14} /></button></div></aside>
    <div className="workspace"><header className="topbar"><span>{title}</span><div>{data.mode === "DEMO" && <Badge tone="warning">Demo mode</Badge>}<span className="topbar-date">{new Date().toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Jakarta" })} · WIB</span><button className="icon-button" aria-label="Open local vault settings" onClick={() => setVaultOpen(true)}><Icon name="shield" size={17} /></button></div></header>
      <main id="main-content" className={`main-content view-${view}`}>{view === "briefing" && <div className="source-alert"><Icon name="radar" size={17} /><p><strong>A deadline worth checking.</strong> UBC’s official award deadline is November 15, earlier than the seed’s December 1.</p><External href="https://undergraduatescholarships.ubc.ca/prog/2027_international_scholars_program_application/">View source</External></div>}{view === "briefing" ? <Briefing {...props} /> : view === "catalogue" ? <Catalogue {...props} /> : view === "bricks" ? <Bricks {...props} /> : <Watchtower {...props} />}</main>
      <footer className="app-footer"><span>StudAb27 <span aria-hidden="true">·</span> A sustainable path, one step at a time.</span><span><Icon name="shield" size={13} />{data.mode === "PRIVATE" ? "Personal data stays in your local vault" : "Fictional demo · no personal profile loaded"}</span></footer>
    </div>
    {toast && <div className={`toast ${toast.error ? "error" : ""}`} role={toast.error ? "alert" : "status"}><Icon name={toast.error ? "radar" : "check"} size={17} /><span>{toast.text}</span><button onClick={() => setToast(null)} aria-label="Dismiss notification" className="icon-button"><Icon name="close" size={15} /></button></div>}
    {route && <RouteDrawer key={route.id} route={route} overlay={data.overlays.find(o => o.routeId === route.id)!} evaluation={data.evaluations.find(e => e.routeId === route.id)!} data={data} act={act} busy={busy} close={() => setRouteId(null)} />}
    {vaultOpen && <VaultDialog data={data} act={act} busy={busy} close={() => setVaultOpen(false)} />}
  </div>;
}

function VaultDialog({ data, act, busy, close }: { data: Dashboard; act: Action; busy: boolean; close: () => void }) {
  const [bundle, setBundle] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  return <Dialog title="Your local vault" onClose={close}><section className="drawer-section vault-intro"><Icon name="shield" size={28} /><h3>{data.mode === "PRIVATE" ? "A workspace that stays with you." : "Explore with a fictional profile."}</h3><p>{data.mode === "PRIVATE" ? "Your profile, strategy, notes, and progress are stored in the ignored private folder on this computer." : "The public demo includes no real student data. Import your own export to create a private local vault."}</p><Badge tone={data.mode === "PRIVATE" ? "success" : "neutral"}>{data.mode === "PRIVATE" ? "Private vault active" : "Demo mode"}</Badge></section><section className="drawer-section"><h3>Your current plan</h3><dl className="reference-list"><div><dt>Graduation</dt><dd>{data.profile.snapshot.expectedGraduation}</dd></div><div><dt>Curriculum</dt><dd>{data.profile.snapshot.curriculum}</dd></div><div><dt>Monthly family cap</dt><dd>IDR {data.profile.snapshot.maxFamilyContributionIdrMPerMonth}M</dd></div><div><dt>SAT planning target</dt><dd>{data.profile.snapshot.satPlan?.targetTotal || "Not set"} · planned, not an achieved score</dd></div></dl></section><section className="drawer-section"><h3>Keep a backup</h3><p>The export includes your profile and private notes. Keep it in a private location. It is not uploaded anywhere by StudAb27.</p><a className="button secondary" href="/api/schola/export" download><Icon name="download" size={16} />Download private JSON backup</a><p className="fine-print">Drive mirror: 00_HQ, 01_Catalogue, 02_Applications, 03_School_Documents, 04_Financial_Documents, 05_Profile_Evidence, 06_Offers_and_Decisions, 07_Inbox, 99_Archive. Cloud and Calendar sync are not connected.</p></section><section className="drawer-section stacked-form"><h3>Restore a StudAb27 export</h3><p>Choose a JSON backup to inspect it. Importing replaces the active profile and progress; a recovery copy is kept locally.</p><label>Backup file<input type="file" accept=".json,application/json" onChange={async e => {
      setError(""); setBundle(null); setConfirmed(false);
      try { const file = e.target.files?.[0]; if (!file) return; if (file.size > 1500000) throw new Error("Backup is too large."); const value = JSON.parse(await file.text()); if (!value || value.format !== "studab27-v1" || !Array.isArray(value.overlays)) throw new Error("Choose a StudAb27 v1 JSON export."); setBundle(value); } catch (err) { setError(err instanceof Error ? err.message : "Could not read backup."); }
    }} /></label>{error && <p role="alert" className="form-error">{error}</p>}{bundle && <><p>Ready to validate {(bundle.overlays as unknown[]).length} route overlays from this backup.</p><label className="checkbox-line"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Replace my current profile and progress with this backup.</label><button className="button primary" disabled={busy || !confirmed} onClick={async () => { if (await act({ action: "import", bundle }, "Backup restored. A recovery copy was kept in the vault.")) close(); }}>{busy ? "Importing…" : "Import into local vault"}</button></>}</section></Dialog>;
}
