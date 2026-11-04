import type { AppState, Overlay, PursuitLevel, Route } from "./schema";

export type PursuitGroup = PursuitLevel | "UNSET";
export const PURSUIT_LABELS: Record<PursuitGroup, string> = { FOCUS: "Focus", SECONDARY: "Secondary", BACKUP: "Backup", UNSET: "Decide later" };
export const PURSUIT_HELP: Record<PursuitGroup, string> = {
  FOCUS: "Work on these regularly.",
  SECONDARY: "Pursue when you have the time.",
  BACKUP: "Keep these open. Their dates still appear in your calendar.",
  UNSET: "Tracked, with priority still to choose.",
};
export const REQUIREMENT_LABELS = { TODO: "Not started", DOING: "In progress", DONE: "Done", NOT_NEEDED: "Not needed" } as const;
export const BASIS_LABELS = { CURRENT: "2027 source", GENERAL: "General guidance", RECHECK: "Recheck for 2027" } as const;
export function pursuitLevel(overlay: Overlay): PursuitGroup { return overlay.pursuitLevel || "UNSET"; }
export function trackedRoutes(routes: Route[], overlays: Overlay[]) {
  const order = { FOCUS: 0, SECONDARY: 1, BACKUP: 2, UNSET: 3 };
  const byId = new Map(overlays.map(o => [o.routeId, o]));
  return routes.filter(r => byId.get(r.id)?.tracked).sort((a, b) => {
    const x = byId.get(a.id)!, y = byId.get(b.id)!;
    return Number(!!y.mainTarget) - Number(!!x.mainTarget) || order[pursuitLevel(x)] - order[pursuitLevel(y)] || a.institution.localeCompare(b.institution);
  });
}
export function guideItems(route: Route, documentsOnly = false) {
  return (route.applicationGuide?.sections.flatMap(s => s.items) || []).filter(i => !documentsOnly || i.kind === "DOCUMENT");
}
export function checklistProgress(route: Route, state: AppState, documentsOnly = false) {
  const items = guideItems(route, documentsOnly), progress = state.requirements?.[route.id] || {};
  const applicable = items.filter(i => !(i.optional && progress[i.id]?.status === "NOT_NEEDED"));
  const done = applicable.filter(i => progress[i.id]?.status === "DONE").length;
  return { total: applicable.length, done, skipped: items.length - applicable.length,
    next: applicable.find(i => progress[i.id]?.status === "DOING") || applicable.find(i => progress[i.id]?.status !== "DONE") };
}
