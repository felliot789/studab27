import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { isWorkspaceView, projectDashboard, WORKSPACE_VIEWS } from "../src/lib/dashboard-view.ts";
import { checklistProgress, trackedRoutes } from "../src/lib/tracker.ts";
import { upcomingEvents } from "../src/lib/calendar.ts";

const read = file => JSON.parse(readFileSync(new URL(`../data/public/${file}`, import.meta.url)));
const guides = read("application_guides.json"), outlooks = read("scholarship_outlooks.json");
const routes = read("scholarships_2027.json").map(route => ({ ...route, applicationGuide: guides[route.id], scholarshipOutlook: outlooks[route.id] }));
const selected = routes.find(route => route.applicationGuide && read("calendar_events.json").some(event => event.routeId === route.id));
const other = routes.find(route => route.id !== selected.id && route.applicationGuide);
const local = { ...routes[0], id: "local-fictional-award", scholarshipName: "Fictional local award", local: true };
const allRoutes = [...routes, local];
const templates = new Map(read("overlay.example.json").map(overlay => [overlay.routeId, overlay]));
const overlays = allRoutes.map(route => ({ applicationStatus: "NOT_STARTED", personalStrategyTier: "", estimatedFamilyGapIdrMPerMonth: "", personalSatTargetNote: "", personalRiskNote: "", ...templates.get(route.id), routeId: route.id, tracked: [selected.id, other.id].includes(route.id) }));
const events = read("calendar_events.json");
const prerequisite = { ...events.find(event => event.routeId !== selected.id), id: "fictional-cross-route-prerequisite" };
const calendarEvents = events.map(event => event.routeId === selected.id ? { ...event, prerequisiteEventIds: [...event.prerequisiteEventIds, prerequisite.id] } : event).concat(prerequisite);
const gate = { status: "UNKNOWN", reason: "Fictional planning check", basis: "Test fixture" };
const data = {
  mode: "DEMO", profile: read("profile.example.json"), routes: allRoutes, overlays, calendarEvents,
  evaluations: allRoutes.map(route => ({ routeId: route.id, curriculum: gate, graduation: gate, budget: { ...gate, gapRange: null }, sat: { status: "UNKNOWN", target: null, scenarioScore: null, basis: "Test fixture" }, overall: "NEEDS_VERIFICATION" })),
  briefing: { cards: read("tasks.json").slice(0, 3), remaining: 4, completed: 1, taskTitles: { "fictional-task": "Fictional completed step" } },
  bricks: read("bricks.json"),
  state: {
    tasks: { "fictional-task": { status: "DONE" } }, bricks: { "fictional:document": true },
    requirements: { [selected.id]: { "fictional-step": { status: "DOING", note: "Fictional saved note" } }, [other.id]: { "another-step": { status: "DONE" } } },
    localScholarships: { [local.id]: local }, scholarshipDrafts: { "fictional-draft": { status: "READY", query: "Fictional public lead" } },
  },
  milestones: [{ date: "2027-01-01", title: "Fictional planning target" }],
  inbox: [{ id: "fictional-capture", text: "Fictional research note", createdAt: "2026-11-16T00:00:00Z", status: "NEW" }],
  sourceNotes: [...read("source_verifications.json"), { id: "fictional-global-note", title: "Global note" }],
  watch: { ...read("watchtower_state.json"), running: true }, schedule: { active: true, label: "Fictional timer" },
};
function freeze(value) { if (value && typeof value === "object" && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
freeze(data);

test("view projection preserves the vault profile and source snapshot without duplicating runtime stores", () => {
  const before = JSON.stringify(data);
  assert.equal(new Set(WORKSPACE_VIEWS).size, WORKSPACE_VIEWS.length);
  for (const view of WORKSPACE_VIEWS) {
    assert.equal(isWorkspaceView(view), true);
    const page = projectDashboard(data, view, selected.id);
    assert.equal(page.profile, data.profile);
    assert.equal(page.mode, data.mode);
    assert.equal(page.watch.running, true);
    assert.equal(page.schedule, data.schedule);
    assert.equal(Object.hasOwn(page.state, "localScholarships"), false);
    assert.equal(Object.hasOwn(page.state, "scholarshipDrafts"), false);
  }
  assert.equal(isWorkspaceView("constructor"), false);
  assert.equal(isWorkspaceView("unknown"), false);
  assert.equal(JSON.stringify(data), before);
});

test("detail keeps all tabs, saved fields, shared documents and cross-route prerequisite titles", () => {
  const page = projectDashboard(data, "detail", selected.id);
  assert.deepEqual(page.routes, [selected]);
  assert.equal(page.routes[0], selected, "the complete guide, evidence and outlook survive hidden tabs");
  assert.deepEqual(page.overlays, data.overlays.filter(overlay => overlay.routeId === selected.id));
  assert.deepEqual(page.evaluations, data.evaluations.filter(evaluation => evaluation.routeId === selected.id));
  assert.deepEqual(page.sourceNotes, data.sourceNotes.filter(note => note.routeId === selected.id));
  assert.deepEqual(page.calendarEvents.filter(event => event.routeId === selected.id), data.calendarEvents.filter(event => event.routeId === selected.id));
  assert.equal(page.calendarEvents.find(event => event.id === prerequisite.id), prerequisite);
  assert.equal(page.bricks, data.bricks, "the plan tab retains reusable pack links");
  assert.equal(page.state.bricks, data.state.bricks);
  assert.deepEqual(page.state.requirements, { [selected.id]: data.state.requirements[selected.id] });
  assert.deepEqual(checklistProgress(page.routes[0], page.state), checklistProgress(selected, data.state));
  assert.deepEqual(page.inbox, []);
  assert.ok(JSON.stringify(page).length < JSON.stringify(data).length / 2);
  assert.equal(projectDashboard(data, "detail", local.id).routes[0], local);
});

test("tracker and documents retain tracked choices, checklist progress and dates without other collections", () => {
  const tracked = trackedRoutes(data.routes, data.overlays);
  const tracker = projectDashboard(data, "tracker"), documents = projectDashboard(data, "bricks");
  for (const page of [tracker, documents]) {
    assert.deepEqual(trackedRoutes(page.routes, page.overlays), tracked);
    for (const route of tracked) assert.deepEqual(checklistProgress(route, page.state), checklistProgress(route, data.state));
    assert.deepEqual(page.sourceNotes, []);
    assert.deepEqual(page.evaluations, []);
    assert.ok(JSON.stringify(page).length < JSON.stringify(data).length / 2);
  }
  const now = new Date("2026-11-03T00:00:00Z");
  const ids = new Set(tracked.map(route => route.id));
  assert.deepEqual(upcomingEvents(tracker.calendarEvents, tracker.overlays, false, now), upcomingEvents(data.calendarEvents, data.overlays, false, now).filter(event => ids.has(event.routeId)));
  assert.equal(documents.bricks, data.bricks);
  assert.equal(documents.state.bricks, data.state.bricks);
  assert.deepEqual(documents.calendarEvents, []);
  assert.deepEqual(projectDashboard({ ...data, overlays: data.overlays.map(overlay => ({ ...overlay, tracked: false })) }, "tracker").routes, []);
});

test("catalogue, calendar and secondary tools retain their interactive data scopes", () => {
  for (const view of ["catalogue", "applications", "calendar", "briefing", "watchtower"]) {
    const page = projectDashboard(data, view);
    assert.equal(page.routes, data.routes, `${view} keeps all selectable route records`);
    assert.equal(page.overlays, data.overlays);
    if (view !== "watchtower") assert.equal(page.calendarEvents, data.calendarEvents);
  }
  assert.equal(projectDashboard(data, "catalogue").evaluations, data.evaluations);
  assert.equal(projectDashboard(data, "applications").evaluations, data.evaluations);
  const calendar = projectDashboard(data, "calendar");
  assert.equal(calendar.milestones, data.milestones);
  assert.deepEqual(calendar.evaluations, []);
  const briefing = projectDashboard(data, "briefing");
  assert.equal(briefing.briefing, data.briefing);
  assert.equal(briefing.state.tasks, data.state.tasks);
  assert.equal(briefing.state.bricks, data.state.bricks);
  assert.equal(briefing.bricks, data.bricks);
  const watchtower = projectDashboard(data, "watchtower");
  assert.equal(watchtower.watch, data.watch);
  assert.equal(watchtower.inbox, data.inbox);
  assert.equal(watchtower.evaluations, data.evaluations);
  assert.equal(watchtower.state.tasks, data.state.tasks);
  for (const view of ["settings", "schola"]) {
    const page = projectDashboard(data, view);
    assert.deepEqual(page.routes, []);
    assert.deepEqual(page.calendarEvents, []);
    assert.deepEqual(page.overlays, []);
    assert.deepEqual(page.inbox, []);
  }
});
