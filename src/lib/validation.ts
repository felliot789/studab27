import { APPLICATION_STATUSES, type AppState, type Overlay, type Profile, type Route, safeUrl } from "./schema";

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Expected a JSON object.");
  return value as Record<string, unknown>;
}
export function text(value: unknown, max = 4000): string {
  if (typeof value !== "string" || value.length > max) throw new Error(`Text must be at most ${max} characters.`);
  return value;
}
export function isoDate(value: unknown): string {
  const date = text(value, 10);
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(parsed.getTime()) || parsed.getUTCFullYear() < 1 || parsed.toISOString().slice(0, 10) !== date) throw new Error("Use a valid ISO calendar date.");
  return date;
}
export function number(value: unknown, min = 0, max = 1000): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) throw new Error(`Number must be between ${min} and ${max}.`);
  return value;
}
export function assertSafeKeys(value: unknown): void {
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    if (["__proto__", "prototype", "constructor"].includes(key)) throw new Error("Unsupported object key.");
    assertSafeKeys(child);
  }
}
export function validateProfile(value: unknown): Profile {
  const p = object(value), snap = object(p.snapshot);
  text(p.projectTitle, 200); text(p.mission, 4000);
  text(snap.curriculum, 500); text(snap.citizenship, 100); text(snap.expectedGraduation, 100);
  number(snap.maxFamilyContributionIdrMPerMonth, 0, 100);
  return value as Profile;
}
export function validateOverlay(value: unknown, ids: Set<string>, historical = false): Overlay {
  const o = object(value);
  if (!ids.has(text(o.routeId, 150))) throw new Error("Unknown scholarship route.");
  if (!APPLICATION_STATUSES.includes(o.applicationStatus as never)) throw new Error("Unknown application status.");
  text(o.personalStrategyTier, 150);
  text(o.estimatedFamilyGapIdrMPerMonth, 300);
  text(o.personalSatTargetNote, 1000); text(o.personalRiskNote, 4000);
  if (o.saved !== undefined && typeof o.saved !== "boolean") throw new Error("Saved must be true or false.");
  for (const field of ["tracked", "mainTarget"]) if (o[field] !== undefined && typeof o[field] !== "boolean") throw new Error(`${field} must be true or false.`);
  if (o.pursuitLevel !== undefined && (typeof o.pursuitLevel !== "string" || !["FOCUS", "SECONDARY", "BACKUP"].includes(o.pursuitLevel))) throw new Error("Unknown pursuit level.");
  if (o.mainTarget && (!o.tracked || o.pursuitLevel !== "FOCUS")) throw new Error("The main target must be tracked as Focus.");
  if (o.notes !== undefined) text(o.notes);
  if (o.costEstimate !== undefined) {
    const cost = object(o.costEstimate);
    for (const key of ["tuition", "housing", "food", "insurance", "other", "coverage"]) number(cost[key], 0, 1000);
    if (cost.upfront !== undefined) number(cost.upfront, 0, 10000);
  }
  if (o.verifiedRules !== undefined) {
    const rule = object(o.verifiedRules);
    if ((historical ? !/^\d{4}$/.test(text(rule.cycle, 4)) : rule.cycle !== "2027") || !safeUrl(text(rule.sourceUrl, 2000))?.startsWith("https://")) throw new Error("A current-cycle HTTPS source is required for a verified rule.");
    if (!text(rule.program, 500).trim()) throw new Error("Name the exact engineering program.");
    isoDate(rule.checkedAt);
    for (const key of ["nationalCurriculumDirectEntry", "preGraduationApplicationAllowed"]) if (rule[key] !== undefined && typeof rule[key] !== "boolean") throw new Error("Rule values must be boolean or omitted when unknown.");
    if (rule.finalDiplomaDeadline !== undefined) isoDate(rule.finalDiplomaDeadline);
  }
  return value as Overlay;
}

export function validateRequirementProgress(value: unknown, routes: Route[], retainedRouteIds?: Set<string>): NonNullable<AppState["requirements"]> {
  const byRoute = object(value);
  for (const [routeId, entries] of Object.entries(byRoute)) {
    const route = routes.find(r => r.id === routeId);
    if (!route && !retainedRouteIds?.has(routeId)) throw new Error("Unknown scholarship checklist.");
    const items = route?.applicationGuide?.sections.flatMap(s => s.items) || [];
    for (const [id, raw] of Object.entries(object(entries))) {
      const item = items.find(i => i.id === id), progress = object(raw);
      if (!item && !retainedRouteIds) throw new Error("Unknown checklist step.");
      text(id, 100);
      if (typeof progress.status !== "string" || !["TODO", "DOING", "DONE", "NOT_NEEDED"].includes(progress.status)) throw new Error("Unknown checklist status.");
      if (progress.status === "NOT_NEEDED" && !retainedRouteIds && item && !item.optional) throw new Error("Only optional or conditional steps can be marked not needed.");
      if (progress.note !== undefined) text(progress.note, 2000);
      if (progress.updatedAt !== undefined && !Number.isFinite(Date.parse(text(progress.updatedAt, 100)))) throw new Error("Invalid checklist date.");
    }
  }
  return byRoute as NonNullable<AppState["requirements"]>;
}
