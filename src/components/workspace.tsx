"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Dashboard } from "@/lib/schema";
import { activeApplication } from "@/lib/calendar";
import Briefing from "./briefing";
import Catalogue from "./catalogue";
import Applications from "./applications";
import Calendar from "./calendar";
import ScholarshipDetail from "./scholarship-detail";
import Bricks from "./bricks";
import Watchtower from "./watchtower";
import ScholaChat from "./schola-chat";
import { Badge, Dialog, Icon, PageHeading, SignOut, type Action } from "./ui";

type View = "briefing" | "catalogue" | "applications" | "calendar" | "bricks" | "watchtower" | "schola" | "settings" | "detail";
const nav = [
  { id: "briefing", href: "/", title: "Today", short: "Today", icon: "home" },
  { id: "catalogue", href: "/scholarships", title: "Scholarships", short: "Scholarships", icon: "compass" },
  { id: "applications", href: "/applications", title: "Applications", short: "Applications", icon: "applications" },
  { id: "calendar", href: "/calendar", title: "Calendar", short: "Calendar", icon: "calendar" },
  { id: "bricks", href: "/documents", title: "Documents", short: "Documents", icon: "layers" },
];

export default function Workspace({ initial, view, routeId, initialTab, calendarRouteId }: { initial: Dashboard; view: View; routeId?: string; initialTab?: string; calendarRouteId?: string }) {
  const router = useRouter();
  const [data, setData] = useState(initial), [busy, setBusy] = useState(false), [vaultOpen, setVaultOpen] = useState(false), [moreOpen, setMoreOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(null);
  const saving = useRef(false);
  useEffect(() => { setData(initial); }, [initial]);
  const refresh = useCallback(async () => {
    const response = await fetch("/api/schola", { cache: "no-store" });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Could not reload your workspace.");
    setData(value);
  }, []);
  useEffect(() => {
    if (view !== "watchtower" && !data.watch.running) return;
    const timer = setInterval(() => refresh().catch(() => setToast({ text: "Could not refresh source status. Displayed observations may be stale.", error: true })), 15000);
    return () => clearInterval(timer);
  }, [view, data.watch.running, refresh]);
  useEffect(() => { if (toast && !toast.error) { const timer = setTimeout(() => setToast(null), 5500); return () => clearTimeout(timer); } }, [toast]);
  const act: Action = async (payload, message) => {
    if (saving.current) return false;
    saving.current = true; setBusy(true);
    try {
      const response = await fetch("/api/schola", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "This change could not be saved.");
      await refresh();
      if (message) setToast({ text: message, error: false });
      return true;
    } catch (error) { setToast({ text: error instanceof Error ? error.message : "Change failed. Your draft is still here.", error: true }); return false; }
    finally { saving.current = false; setBusy(false); }
  };
  const props = { data, act, busy, openRoute: (id: string) => router.push(`/scholarships/${id}`) };
  const activeView = view === "detail" ? "catalogue" : view;
  const title = nav.find(n => n.id === activeView)?.title || ({ watchtower: "Source updates", settings: "Settings", schola: "Schola" } as Record<string, string>)[view];
  const activeCount = data.overlays.filter(activeApplication).length;
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to content</a><aside className="sidebar"><Link href="/" className="brand" aria-label="StudAb27 home"><span className="brand-mark">S<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 10 10 2M3 2h7v7" /></svg></span><span>StudAb<span className="brand-year">27</span></span></Link><span className="sidebar-subtitle">Scholarship planning</span><nav aria-label="Main navigation">{nav.map(item => <Link key={item.id} href={item.href} className={activeView === item.id ? "nav-link active" : "nav-link"} aria-current={activeView === item.id ? "page" : undefined}><Icon name={item.icon} size={19} /><span>{item.title}</span>{item.id === "applications" && activeCount > 0 && <small>{activeCount}</small>}</Link>)}</nav><div className="sidebar-bottom"><Link href="/schola" className={`schola-entry ${view === "schola" ? "current" : ""}`}><span className="schola-star" aria-hidden="true">✳</span><span><strong>Ask Schola</strong><small>Scholarship research assistant</small></span><Icon name="arrow" size={15} /></Link><nav className="secondary-nav" aria-label="Workspace tools"><Link className={`nav-link ${view === "watchtower" ? "active" : ""}`} href="/updates"><Icon name="radar" size={17} />Source updates</Link><Link className={`nav-link ${view === "settings" ? "active" : ""}`} href="/settings"><Icon name="settings" size={17} />Settings</Link></nav><button className="vault-button" onClick={() => setVaultOpen(true)}><span className="vault-avatar"><Icon name="shield" size={17} /></span><span><strong>{data.mode === "PRIVATE" ? "Private workspace" : "Demo workspace"}</strong><small>{data.mode === "PRIVATE" ? "Your vault · this device" : "Fictional sample profile"}</small></span><Icon name="chevron" size={14} /></button></div></aside>
    <div className="workspace"><header className="topbar"><Link href="/" className="mobile-brand">StudAb<span>27</span></Link><span className="topbar-location">{title}</span><div>{data.mode === "DEMO" && <Badge tone="warning">Demo</Badge>}<Link className="ask-schola" href="/schola"><Icon name="chat" size={17} /><span>Ask Schola</span></Link><button className="icon-button mobile-more" aria-label="More workspace tools" onClick={() => setMoreOpen(true)}><Icon name="more" /></button></div></header>
      <main id="main-content" className={`main-content view-${view}`}>{view === "briefing" ? <Briefing {...props} /> : view === "catalogue" ? <Catalogue {...props} /> : view === "applications" ? <Applications {...props} /> : view === "calendar" ? <Calendar key={calendarRouteId || "my-calendar"} {...props} initialRouteId={calendarRouteId} /> : view === "detail" && routeId ? <ScholarshipDetail key={routeId} {...props} routeId={routeId} initialTab={initialTab} /> : view === "bricks" ? <Bricks {...props} /> : view === "schola" ? <ScholaChat /> : view === "settings" ? <><PageHeading title="Settings">Your profile, privacy, and backups, in one place.</PageHeading><section className="settings-section"><h2>Your current plan</h2><dl className="reference-list"><div><dt>Graduation</dt><dd>{data.profile.snapshot.expectedGraduation}</dd></div><div><dt>Curriculum</dt><dd>{data.profile.snapshot.curriculum}</dd></div><div><dt>Monthly family cap</dt><dd>IDR {data.profile.snapshot.maxFamilyContributionIdrMPerMonth}M</dd></div><div><dt>SAT planning target</dt><dd>{data.profile.snapshot.satPlan?.targetTotal || "Not set"} · planned, not achieved</dd></div></dl></section><section className="settings-section"><h2>Your data</h2><p>Profile, strategy, notes, and progress are kept in your local vault. Download a backup or restore an earlier export.</p><button className="button secondary" onClick={() => setVaultOpen(true)}><Icon name="shield" size={17} />Open vault & backups</button></section><section className="settings-section"><h2>Research tools</h2><p>Check source changes, capture research notes, or try a budget and SAT scenario.</p><Link href="/updates" className="text-button">Open source updates & scenarios<Icon name="arrow" size={16} /></Link></section></> : <Watchtower {...props} />}</main>
      {view !== "schola" && <footer className="app-footer"><span>StudAb27</span><span><Icon name="shield" size={13} />{data.mode === "PRIVATE" ? "Your private workspace" : "Fictional demo · no personal profile loaded"}</span></footer>}
    </div><nav className="mobile-nav" aria-label="Mobile navigation">{nav.map(item => <Link key={item.id} href={item.href} aria-current={activeView === item.id ? "page" : undefined}><Icon name={item.icon} size={21} /><span>{item.short}</span></Link>)}</nav>
    {toast && <div className={`toast ${toast.error ? "error" : ""}`} role={toast.error ? "alert" : "status"}><Icon name={toast.error ? "radar" : "check"} size={17} /><span>{toast.text}</span><button onClick={() => setToast(null)} aria-label="Dismiss notification" className="icon-button"><Icon name="close" size={15} /></button></div>}
    {vaultOpen && <VaultDialog data={data} act={act} busy={busy} close={() => setVaultOpen(false)} />}
    {moreOpen && <Dialog title="Your workspace" onClose={() => setMoreOpen(false)}><nav className="more-links"><Link href="/schola"><Icon name="chat" />Ask Schola</Link><Link href="/updates"><Icon name="radar" />Source updates & scenarios</Link><Link href="/settings"><Icon name="settings" />Settings & backups</Link></nav></Dialog>}
  </div>;
}

function VaultDialog({ data, act, busy, close }: { data: Dashboard; act: Action; busy: boolean; close: () => void }) {
  const [bundle, setBundle] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  return <Dialog title="Your local vault" onClose={close}><section className="drawer-section vault-intro"><Icon name="shield" size={28} /><h3>{data.mode === "PRIVATE" ? "Private vault" : "Demo workspace"}</h3><p>{data.mode === "PRIVATE" ? "Your profile, strategy, notes, and progress are stored in the ignored private folder on this computer." : "The public demo includes no real student data. Import your own export to create a private local vault."}</p><Badge tone={data.mode === "PRIVATE" ? "success" : "neutral"}>{data.mode === "PRIVATE" ? "Private vault active" : "Demo mode"}</Badge></section><section className="drawer-section"><h3>Your current plan</h3><dl className="reference-list"><div><dt>Graduation</dt><dd>{data.profile.snapshot.expectedGraduation}</dd></div><div><dt>Curriculum</dt><dd>{data.profile.snapshot.curriculum}</dd></div><div><dt>Monthly family cap</dt><dd>IDR {data.profile.snapshot.maxFamilyContributionIdrMPerMonth}M</dd></div><div><dt>SAT planning target</dt><dd>{data.profile.snapshot.satPlan?.targetTotal || "Not set"} · planned, not an achieved score</dd></div></dl></section><section className="drawer-section"><h3>Backups</h3><p>The export includes your profile and private notes. Keep it in a private location. It is not uploaded anywhere by StudAb27.</p><a className="button secondary" href="/api/schola/export" download><Icon name="download" size={16} />Download private JSON backup</a><p className="fine-print">Drive mirror: 00_HQ, 01_Catalogue, 02_Applications, 03_School_Documents, 04_Financial_Documents, 05_Profile_Evidence, 06_Offers_and_Decisions, 07_Inbox, 99_Archive. Cloud and Calendar sync are not connected.</p></section><section className="drawer-section stacked-form"><h3>Restore a StudAb27 export</h3><p>Choose a JSON backup to inspect it. Importing replaces the active profile and progress; a recovery copy is kept locally.</p><label>Backup file<input type="file" accept=".json,application/json" onChange={async e => {
      setError(""); setBundle(null); setConfirmed(false);
      try { const file = e.target.files?.[0]; if (!file) return; if (file.size > 1500000) throw new Error("Backup is too large."); const value = JSON.parse(await file.text()); if (!value || value.format !== "studab27-v1" || !Array.isArray(value.overlays)) throw new Error("Choose a StudAb27 v1 JSON export."); setBundle(value); } catch (err) { setError(err instanceof Error ? err.message : "Could not read backup."); }
    }} /></label>{error && <p role="alert" className="form-error">{error}</p>}{bundle && <><p>Ready to validate {(bundle.overlays as unknown[]).length} route overlays from this backup.</p><label className="checkbox-line"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Replace my current profile and progress with this backup.</label><button className="button primary" disabled={busy || !confirmed} onClick={async () => { if (await act({ action: "import", bundle }, "Backup restored. A recovery copy was kept in the vault.")) close(); }}>{busy ? "Importing…" : "Import into local vault"}</button></>}</section><SignOut /></Dialog>;
}
