"use client";
import Link from "next/link";
import { useState } from "react";
import { gapText, label } from "@/lib/schema";
import { activeApplication, dateLabel, eventDay, upcomingEvents } from "@/lib/calendar";
import { Badge, Icon, PageHeading, type ViewProps } from "./ui";

export default function Catalogue({ data, act, busy }: ViewProps) {
  const [query, setQuery] = useState(""), [country, setCountry] = useState("all"), [scope, setScope] = useState("all");
  const [tier, setTier] = useState("all"), [budget, setBudget] = useState("all");
  const filtered = data.routes.filter(r => {
    const o = data.overlays.find(o => o.routeId === r.id)!, e = data.evaluations.find(e => e.routeId === r.id)!;
    return `${r.institution} ${r.scholarshipName} ${r.country}`.toLowerCase().includes(query.toLowerCase()) && (country === "all" || country === r.country) && (scope === "all" || o.saved) && (tier === "all" || tier === o.personalStrategyTier) && (budget === "all" || budget === e.budget.status);
  });
  const next = upcomingEvents(data.calendarEvents, data.overlays, true);
  const savedCount = data.overlays.filter(o => o.saved).length;
  return <><PageHeading title="Scholarships">Search 57 scholarship routes and save scholarships to track their deadlines.</PageHeading>
    <div className="discovery-tools"><label className="search-box"><Icon name="search" /><input type="search" aria-label="Search scholarships" placeholder="University, scholarship, or country" value={query} onChange={e => setQuery(e.target.value)} /></label><label className="sr-only" htmlFor="country">Country</label><select id="country" value={country} onChange={e => setCountry(e.target.value)}><option value="all">All countries</option>{[...new Set(data.routes.map(r => r.country))].sort().map(c => <option key={c}>{c}</option>)}</select></div>
    <div className="discovery-tabs"><div className="text-tabs" role="group" aria-label="Scholarship selection"><button aria-pressed={scope === "all"} onClick={() => setScope("all")}>All scholarships <span>{data.routes.length}</span></button><button aria-pressed={scope === "saved"} onClick={() => setScope("saved")}>Saved <span>{savedCount}</span></button></div><details className="research-filters"><summary><Icon name="filter" size={16} />More filters{(tier !== "all" || budget !== "all") && " · active"}</summary><div><label>Strategy<select value={tier} onChange={e => setTier(e.target.value)}><option value="all">All strategy tiers</option>{[...new Set(data.overlays.map(o => o.personalStrategyTier))].sort().map(t => <option key={t}>{t}</option>)}</select></label><label>Monthly budget estimate<select value={budget} onChange={e => setBudget(e.target.value)}><option value="all">All budget estimates</option><option value="PASS">Within family cap</option><option value="FAIL">Over family cap</option><option value="UNKNOWN">Still to estimate</option></select></label></div></details></div>
    <div className="section-line list-caption"><span>{filtered.length} scholarship{filtered.length === 1 ? "" : "s"}</span><span>2027 entry · research reviewed 3 Nov 2026</span></div>
    <div className="scholarship-list">{filtered.map(r => {
      const o = data.overlays.find(o => o.routeId === r.id)!, e = data.evaluations.find(e => e.routeId === r.id)!, date = next.find(n => n.routeId === r.id);
      return <article className="scholarship-row" key={r.id}><div className="scholarship-identity"><span className="eyebrow">{r.country}{activeApplication(o) && <Badge>{label(o.applicationStatus)}</Badge>}</span><h2><Link href={`/scholarships/${r.id}`}>{r.institution}<Icon name="arrow" size={18} /></Link></h2><p>{r.scholarshipName}</p><span className="research-caption">{r.fundingType} · award terms to verify</span></div><div className="scholarship-next"><span>Next published date</span><strong>{date ? dateLabel(eventDay(date)!, true) : "Dates to confirm"}</strong>{date && <small>{date.title}</small>}<small>Monthly gap estimate: {gapText(e)}</small></div><button className={`save-button ${o.saved ? "saved" : ""}`} disabled={busy} aria-pressed={!!o.saved} aria-label={`${o.saved ? "Unsave" : "Save"} ${r.institution}`} onClick={() => act({ action: "overlay", id: r.id, patch: { saved: !o.saved } }, o.saved ? "Scholarship removed from saved routes." : "Scholarship saved. Its dates are in your calendar.")}><Icon name={o.saved ? "bookmark-filled" : "bookmark"} size={19} /><span>{o.saved ? "Saved" : "Save"}</span></button></article>;
    })}</div>
    {!filtered.length && <div className="empty-state"><Icon name="bookmark" size={30} /><h2>{scope === "saved" && !savedCount ? "No saved scholarships" : "No scholarships match."}</h2><p>{scope === "saved" && !savedCount ? "Save scholarships from the catalogue to add them to your shortlist and calendar." : "Try another search or clear the filters."}</p><button className="button primary" onClick={() => { setScope("all"); setQuery(""); setCountry("all"); setTier("all"); setBudget("all"); }}>Browse scholarships</button></div>}
    <p className="end-note">Funding descriptions are research leads. Open a scholarship to see what has evidence and what still needs checking.</p>
  </>;
}
