"use client";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { safeUrl, type Dashboard } from "@/lib/schema";

export type Action = (payload: Record<string, unknown>, message?: string) => Promise<boolean>;
export type ViewProps = { data: Dashboard; act: Action; busy: boolean; openRoute: (id: string) => void };
const countryFlags: Record<string, string> = {
  Brunei: "🇧🇳", Canada: "🇨🇦", China: "🇨🇳", "Hong Kong": "🇭🇰", Hungary: "🇭🇺",
  Italy: "🇮🇹", Qatar: "🇶🇦", Romania: "🇷🇴", Singapore: "🇸🇬", "South Korea": "🇰🇷",
  Taiwan: "🇹🇼", Türkiye: "🇹🇷", UAE: "🇦🇪", "United Kingdom": "🇬🇧", "United States": "🇺🇸",
};
export function CountryFlag({ country, labelled = false }: { country: string; labelled?: boolean }) {
  const flag = countryFlags[country];
  return flag ? <span className="country-flag" title={country} role={labelled ? "img" : undefined} aria-label={labelled ? country : undefined} aria-hidden={labelled ? undefined : true}>{flag}</span> : null;
}
export function CountryLabel({ country }: { country: string }) { return <span className="country-label"><CountryFlag country={country} />{country}</span>; }
const paths: Record<string, string> = {
  home: "m3 10 9-7 9 7v10H3Zm6 10v-7h6v7", compass: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm4-16-2 8-8 2 2-8Z",
  layers: "m3 7 9-5 9 5-9 5Zm0 5 9 5 9-5M3 17l9 5 9-5", radar: "M12 2v10l7 7M20.7 7A10 10 0 1 1 7 3M12 7a5 5 0 1 0 5 5",
  arrow: "M4 12h15m-6-6 6 6-6 6", external: "M14 3h7v7m0-7L10 14M10 3H3v18h18v-7", clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-16v6l4 2",
  check: "m5 12 4 4L19 6", chevron: "m9 5 7 7-7 7", close: "m6 6 12 12M6 18 18 6", search: "M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 6 6",
  shield: "m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Zm-4 9 3 3 5-6", download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  pause: "M8 4v16M16 4v16", play: "m7 3 14 9-14 9Z", refresh: "M20 7a9 9 0 1 0 1 8M20 2v5h-5", plus: "M12 4v16M4 12h16", moon: "M20 15A9 9 0 0 1 9 3 9 9 0 1 0 20 15Z",
  chat: "M21 11a9 9 0 0 1-9 9H5l-4 3 2-7A9 9 0 1 1 21 11ZM7 10h10M7 14h6",
  calendar: "M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2ZM7 2v5M17 2v5M3 10h18M7 14h2M12 14h2M7 17h2",
  bookmark: "M6 3h12v19l-6-4-6 4Z", "bookmark-filled": "M6 3h12v19l-6-4-6 4ZM9 9l2 2 4-4",
  applications: "M8 6V3h8v3M3 7h18v14H3ZM3 12a22 22 0 0 0 18 0M10 12v3h4v-3",
  back: "m15 5-7 7 7 7", filter: "M4 6h16M7 12h10M10 18h4",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1Z",
  more: "M5 12h.01M12 12h.01M19 12h.01",
};
export function Icon({ name, size = 18 }: { name: string; size?: number }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.compass} /></svg>; }
export function External({ href, children, className = "" }: { href?: string; children: ReactNode; className?: string }) { const url = href && safeUrl(href); return url ? <a href={url} target="_blank" rel="noopener noreferrer" className={`source-link ${className}`}>{children}<Icon name="external" size={13} /></a> : <span>{children}</span>; }
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span>; }
export function Dialog({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => { const d = ref.current, prior = document.body.style.overflow; document.body.style.overflow = "hidden"; d?.showModal(); return () => { d?.close(); document.body.style.overflow = prior; }; }, []);
  return <dialog ref={ref} aria-labelledby={titleId} aria-modal="true" className={`drawer ${wide ? "wide" : ""}`} onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }}><div className="drawer-inner"><header className="drawer-header"><h2 id={titleId}>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><Icon name="close" /></button></header>{children}</div></dialog>;
}
export function PageHeading({ title, children, extra }: { title: string; children: ReactNode; extra?: ReactNode }) { return <header className="page-heading"><div><h1>{title}</h1><p>{children}</p></div>{extra}</header>; }
export function shortDate(date: string) { return new Date(date.length === 10 ? `${date}T12:00:00+07:00` : date).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Asia/Jakarta" }); }
export function dateTime(date: string) { return new Date(date).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" }) + " WIB"; }
export function SignOut() {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  return <section className="drawer-section"><h3>This browser</h3><button className="button secondary" disabled={busy} onClick={async () => {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "logout" }) });
      if (!response.ok) throw new Error("Sign-out is unavailable. Login may not be configured in this demo.");
      window.location.assign("/login");
    } catch (err) { setError((err as Error).message); setBusy(false); }
  }}>{busy ? "Signing out…" : "Sign out of this browser"}</button>{error && <p className="form-error" role="alert">{error}</p>}</section>;
}
