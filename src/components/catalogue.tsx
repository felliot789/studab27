"use client";
import Link from "next/link";
import { useState } from "react";
import { gapText, label } from "@/lib/schema";
import { activeApplication, dateLabel, eventDay, upcomingEvents } from "@/lib/calendar";
import type { OutlookCategory } from "@/lib/schema";
import { OUTLOOK_CATEGORIES, OUTLOOK_EXPLANATIONS, OUTLOOK_LABELS, matchesOutlook, outlookCategory } from "@/lib/scholarship-outlook";
import ScholarshipOutlook from "./scholarship-outlook";
import ScholarshipDraftsButton from "./scholarship-drafts";
import { Badge, CountryLabel, Icon, PageHeading, type ViewProps } from "./ui";

export default function Catalogue({ data, act, busy }: ViewProps) {
  const [query, setQuery] = useState(""), [country, setCountry] = useState("all"), [scope, setScope] = useState("all");
  const [tier, setTier] = useState("all"), [budget, setBudget] = useState("all");
  const [outlook, setOutlook] = useState<OutlookCategory | "ALL">("ALL"), [hideLottery, setHideLottery] = useState(false);
  const matching = data.routes.filter(r => {
    const o = data.overlays.find(o => o.routeId === r.id)!, e = data.evaluations.find(e => e.routeId === r.id)!;
    return `${r.institution} ${r.scholarshipName} ${r.country}`.toLowerCase().includes(query.toLowerCase()) && (country === "all" || country === r.country) && (scope === "all" || o.tracked) && (tier === "all" || tier === o.personalStrategyTier) && (budget === "all" || budget === e.budget.status);
  });
  const filtered = matching.filter(r => matchesOutlook(r, outlook, hideLottery));
  const clearFilters = () => { setScope("all"); setQuery(""); setCountry("all"); setTier("all"); setBudget("all"); setOutlook("ALL"); setHideLottery(false); };
  const hasFilters = !!query || country !== "all" || tier !== "all" || budget !== "all" || scope !== "all" || outlook !== "ALL" || hideLottery;
  const next = upcomingEvents(data.calendarEvents, data.overlays, true);
  const trackedCount = data.overlays.filter(o => o.tracked).length;
  return <><nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/scholarships"><Icon name="back" size={16} />Back to tracker</Link></nav><PageHeading title="Explore scholarships" extra={<ScholarshipDraftsButton />}>Browse scholarships, compare evidence, and add applications to the tracker.</PageHeading>
    <section className="outlook-organizer" aria-labelledby="outlook-heading">
      <div className="section-line"><h2 id="outlook-heading">Scholarship outlook</h2><span>Admission + award selection</span></div>
      <p id="outlook-help" role="status">{outlook === "ALL" ? "Outlooks assess admission and award selection. They do not establish individual award probabilities." : OUTLOOK_EXPLANATIONS[outlook]}</p>
      <div className="outlook-filters" role="group" aria-label="Scholarship outlook" aria-describedby="outlook-help">
        <button aria-pressed={outlook === "ALL" && !hideLottery} onClick={() => { setOutlook("ALL"); setHideLottery(false); }}>All outlooks <span>{matching.length}</span></button>
        {OUTLOOK_CATEGORIES.map(category => <button key={category} aria-pressed={outlook === category} onClick={() => { setOutlook(category); setHideLottery(false); }}>{OUTLOOK_LABELS[category]} <span>{matching.filter(r => outlookCategory(r) === category).length}</span></button>)}
      </div>
      <div className="outlook-options"><label><input type="checkbox" checked={hideLottery} onChange={event => { setHideLottery(event.target.checked); if (outlook === "LOTTERY") setOutlook("ALL"); }} />Hide lottery options</label><details className="outlook-guide"><summary>What the labels mean</summary><dl>{OUTLOOK_CATEGORIES.map(category => <div key={category}><dt>{OUTLOOK_LABELS[category]}</dt><dd>{OUTLOOK_EXPLANATIONS[category]}</dd></div>)}</dl><p>Admission-linked funding is not automatically Realistic. Percentages appear only for a sourced scholarship recipient/applicant cohort, with its year and scope. Unknown options remain visible unless filtered out.</p></details></div>
    </section>
    <div className="discovery-tools"><label className="search-box"><Icon name="search" /><input type="search" aria-label="Search scholarships" placeholder="University, scholarship, or country" value={query} onChange={e => setQuery(e.target.value)} /></label><label className="sr-only" htmlFor="country">Country</label><select id="country" value={country} onChange={e => setCountry(e.target.value)}><option value="all">All countries</option>{[...new Set(data.routes.map(r => r.country))].sort().map(c => <option key={c}>{c}</option>)}</select></div>
    <div className="discovery-tabs"><div className="text-tabs" role="group" aria-label="Scholarship selection"><button aria-pressed={scope === "all"} onClick={() => setScope("all")}>All scholarships <span>{data.routes.length}</span></button><button aria-pressed={scope === "tracked"} onClick={() => setScope("tracked")}>Tracked <span>{trackedCount}</span></button></div><details className="research-filters"><summary><Icon name="filter" size={16} />More filters{(tier !== "all" || budget !== "all") && " · active"}</summary><div><label>Strategy<select value={tier} onChange={e => setTier(e.target.value)}><option value="all">All strategy tiers</option>{[...new Set(data.overlays.map(o => o.personalStrategyTier))].sort().map(t => <option key={t}>{t}</option>)}</select></label><label>Monthly budget estimate<select value={budget} onChange={e => setBudget(e.target.value)}><option value="all">All budget estimates</option><option value="PASS">Within family cap</option><option value="FAIL">Over family cap</option><option value="UNKNOWN">Still to estimate</option></select></label></div></details></div>
    <div className="section-line list-caption"><span role="status">{filtered.length} scholarship{filtered.length === 1 ? "" : "s"}{hideLottery ? " · lottery hidden" : ""}</span>{hasFilters ? <button className="text-button" onClick={clearFilters}>Clear filters</button> : <span>2027 entry · open a label for its evidence</span>}</div>
    <div className="scholarship-list">{filtered.map(r => {
      const o = data.overlays.find(o => o.routeId === r.id)!, e = data.evaluations.find(e => e.routeId === r.id)!, date = next.find(n => n.routeId === r.id);
      return <article className="scholarship-row" key={r.id}><div className="scholarship-identity"><span className="eyebrow"><CountryLabel country={r.country} />{activeApplication(o) && <Badge>{label(o.applicationStatus)}</Badge>}</span><h2><Link href={`/scholarships/${r.id}?tab=overview`}>{r.institution}<Icon name="arrow" size={18} /></Link></h2><p>{r.scholarshipName}</p><ScholarshipOutlook route={r} /><span className="research-caption">{r.fundingType} · award terms to verify</span></div><div className="scholarship-next"><span>Next published date</span><strong>{date ? dateLabel(eventDay(date)!, true) : "Dates to confirm"}</strong>{date && <small>{date.title}</small>}<small>Monthly gap estimate: {gapText(e)}</small></div><button className={`save-button ${o.tracked ? "saved" : ""}`} disabled={busy} aria-pressed={!!o.tracked} aria-label={`${o.tracked ? "Stop tracking" : "Track"} ${r.institution}`} onClick={() => act({ action: "tracking", id: r.id, command: o.tracked ? "remove" : "add" }, o.tracked ? "Removed from tracker. Progress retained." : "Scholarship added to tracker.")}><Icon name={o.tracked ? "bookmark-filled" : "bookmark"} size={19} /><span>{o.tracked ? "Tracking" : "Track"}</span></button></article>;
    })}</div>
    {!filtered.length && <div className="empty-state"><Icon name="bookmark" size={30} /><h2>{scope === "tracked" && !trackedCount ? "No tracked scholarships" : outlook === "REALISTIC" ? "No options assessed as Realistic in this selection" : "No scholarships match"}</h2><p>{scope === "tracked" && !trackedCount ? "Track a scholarship to keep its progress and dates together." : outlook === "REALISTIC" ? "A generous award or a budget match does not establish a realistic path. Explore Unknown options for missing evidence, or broaden the filters." : "Try another outlook or clear the filters."}</p><button className="button primary" onClick={clearFilters}>Show all scholarships</button></div>}
    <p className="end-note">Funding descriptions are research leads. Open a scholarship to see what has evidence and what still needs checking.</p>
  </>;
}
