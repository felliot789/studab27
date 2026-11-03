import type { CalendarEvent, Overlay } from "./schema";

export function activeApplication(overlay: Overlay) {
  return !["NOT_STARTED", "DROP"].includes(overlay.applicationStatus);
}
export function inMyCalendar(overlay: Overlay) { return !!overlay.saved || activeApplication(overlay); }
export function todayWib(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}
// Only source-supported dates may occupy a calendar day. Recurring rules and
// conflicting sources remain visible in the dates-to-confirm list.
export function eventDay(event: CalendarEvent): string | null {
  return event.calendarDateSupported && event.sourceReview.status === "SOURCE_SUPPORTED_FOR_TARGET_CYCLE"
    ? event.deadlineAtWib?.slice(0, 10) || event.date : null;
}
export function eventEndDay(event: CalendarEvent): string | null { return eventDay(event) ? event.endDate || eventDay(event) : null; }
export function eventClock(event: CalendarEvent) {
  return event.deadlineAtWib
    ? new Date(event.deadlineAtWib).toLocaleTimeString("en-GB", { timeZone: "Asia/Jakarta", hour: "2-digit", minute: "2-digit" }) + " WIB"
    : event.cutoffTimeText ? `${event.cutoffTimeText} · time zone to confirm` : "Cutoff time not published";
}
export function dateLabel(date: string, year = false) {
  return new Date(date + "T12:00:00+07:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}), timeZone: "Asia/Jakarta" });
}
export function eventKind(event: CalendarEvent) {
  const type = event.eventType;
  return type.includes("OPEN") ? "Opens" : type.includes("TEST") ? "Tests" : type.includes("ACCEPTANCE") ? "Accept offer" : type.includes("INTERVIEW") ? "Interview" : type.includes("NOMINATION") ? "Nomination" : type.includes("REFERENCE") ? "Reference" : type.includes("DOCUMENT") ? "Documents" : type.includes("DECISION") || type.includes("RESULT") ? "Decision" : type.includes("FINANCIAL") || type.includes("AID") ? "Financial aid" : "Apply";
}
export function dateConfidence(event: CalendarEvent) {
  if (eventDay(event)) return "Published for this cycle";
  if (event.sourceReview.status === "CONFLICTING_OFFICIAL_SOURCES") return "Sources disagree";
  if (event.sourceReview.status === "OFFICIAL_RECURRING_RULE_YEAR_UNCONFIRMED") return "Annual rule · cycle unconfirmed";
  return "Date to confirm";
}
export function upcomingEvents(events: CalendarEvent[], overlays: Overlay[], all = false, now = new Date()) {
  const ids = new Set(overlays.filter(inMyCalendar).map(o => o.routeId));
  return events.filter(e => (all || ids.has(e.routeId)) && eventDay(e) && eventEndDay(e)! >= todayWib(now)
    && (!e.deadlineAtWib || e.endDate || Date.parse(e.deadlineAtWib) >= now.getTime()))
    .sort((a, b) => eventDay(a)!.localeCompare(eventDay(b)!) || (a.deadlineAtWib || "").localeCompare(b.deadlineAtWib || "") || a.id.localeCompare(b.id));
}
