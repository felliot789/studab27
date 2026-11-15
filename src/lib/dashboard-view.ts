import type { Dashboard } from "./schema";

export const WORKSPACE_VIEWS = ["tracker", "briefing", "catalogue", "applications", "calendar", "bricks", "watchtower", "schola", "settings", "detail"] as const;
export type WorkspaceView = typeof WORKSPACE_VIEWS[number];
export function isWorkspaceView(value: string): value is WorkspaceView {
  return WORKSPACE_VIEWS.some(view => view === value);
}

// Page payloads retain complete records for the visible view. Storage and exports
// keep the full snapshot; hidden detail tabs and the vault need no follow-up load.
export function projectDashboard(data: Dashboard, view: WorkspaceView, routeId?: string): Dashboard {
  const projected: Dashboard = {
    ...data,
    routes: [], overlays: [], evaluations: [], calendarEvents: [], bricks: [],
    briefing: { cards: [], remaining: 0, completed: 0, taskTitles: {} },
    state: { tasks: {}, bricks: {} }, milestones: [], inbox: [], sourceNotes: [],
    watch: { lastRunAt: null, running: data.watch.running, sources: {}, events: [] },
  };
  if (view === "tracker" || view === "bricks" || view === "detail") {
    const ids = new Set(view === "detail" ? routeId ? [routeId] : [] : data.overlays.filter(overlay => overlay.tracked).map(overlay => overlay.routeId));
    projected.routes = data.routes.filter(route => ids.has(route.id));
    projected.overlays = data.overlays.filter(overlay => ids.has(overlay.routeId));
    projected.state = { tasks: {}, bricks: data.state.bricks, requirements: Object.fromEntries(Object.entries(data.state.requirements || {}).filter(([id]) => ids.has(id))) };
    if (view !== "tracker") projected.bricks = data.bricks;
    if (view !== "bricks") {
      const events = data.calendarEvents.filter(event => ids.has(event.routeId));
      const prerequisites = new Set(events.flatMap(event => event.prerequisiteEventIds));
      projected.calendarEvents = data.calendarEvents.filter(event => ids.has(event.routeId) || prerequisites.has(event.id));
    }
    if (view === "detail") {
      projected.evaluations = data.evaluations.filter(evaluation => ids.has(evaluation.routeId));
      projected.sourceNotes = data.sourceNotes.filter(note => !!note.routeId && ids.has(note.routeId));
    }
    return projected;
  }
  if (view === "catalogue" || view === "applications" || view === "calendar" || view === "briefing" || view === "watchtower") {
    projected.routes = data.routes;
    projected.overlays = data.overlays;
  }
  if (view === "catalogue" || view === "applications" || view === "watchtower") projected.evaluations = data.evaluations;
  if (view === "catalogue" || view === "applications" || view === "calendar" || view === "briefing") projected.calendarEvents = data.calendarEvents;
  if (view === "calendar") projected.milestones = data.milestones;
  if (view === "briefing") {
    projected.briefing = data.briefing;
    projected.bricks = data.bricks;
    projected.state = { tasks: data.state.tasks, bricks: data.state.bricks };
  }
  if (view === "watchtower") {
    projected.watch = data.watch;
    projected.inbox = data.inbox;
    projected.state = { tasks: data.state.tasks, bricks: {} };
  }
  return projected;
}
