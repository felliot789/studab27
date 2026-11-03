import { APPLICATION_STATUSES, type Overlay, type Profile, safeUrl } from "./schema";

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Expected a JSON object.");
  return value as Record<string, unknown>;
}
export function text(value: unknown, max = 4000): string {
  if (typeof value !== "string" || value.length > max) throw new Error(`Text must be at most ${max} characters.`);
  return value;
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
export function validateOverlay(value: unknown, ids: Set<string>): Overlay {
  const o = object(value);
  if (!ids.has(text(o.routeId, 150))) throw new Error("Unknown scholarship route.");
  if (!APPLICATION_STATUSES.includes(o.applicationStatus as never)) throw new Error("Unknown application status.");
  text(o.personalStrategyTier, 150);
  text(o.estimatedFamilyGapIdrMPerMonth, 300);
  text(o.personalSatTargetNote, 1000); text(o.personalRiskNote, 4000);
  if (o.saved !== undefined && typeof o.saved !== "boolean") throw new Error("Saved must be true or false.");
  if (o.notes !== undefined) text(o.notes);
  if (o.costEstimate !== undefined) {
    const cost = object(o.costEstimate);
    for (const key of ["tuition", "housing", "food", "insurance", "other", "coverage"]) number(cost[key], 0, 1000);
    if (cost.upfront !== undefined) number(cost.upfront, 0, 10000);
  }
  if (o.verifiedRules !== undefined) {
    const rule = object(o.verifiedRules);
    if (rule.cycle !== "2027" || !safeUrl(text(rule.sourceUrl, 2000))?.startsWith("https://")) throw new Error("A current-cycle HTTPS source is required for a verified rule.");
    if (!text(rule.program, 500).trim()) throw new Error("Name the exact engineering program.");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text(rule.checkedAt, 10)) || !Number.isFinite(Date.parse(rule.checkedAt as string))) throw new Error("A valid checked date is required.");
    for (const key of ["nationalCurriculumDirectEntry", "preGraduationApplicationAllowed"]) if (rule[key] !== undefined && typeof rule[key] !== "boolean") throw new Error("Rule values must be boolean or omitted when unknown.");
    if (rule.finalDiplomaDeadline !== undefined && !/^\d{4}-\d{2}-\d{2}$/.test(text(rule.finalDiplomaDeadline, 10))) throw new Error("Use an ISO diploma deadline date.");
  }
  return value as Overlay;
}
