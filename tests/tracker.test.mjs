import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { checklistProgress, guideItems, pursuitLevel, trackedRoutes } from "../src/lib/tracker.ts";
import { inMyCalendar } from "../src/lib/calendar.ts";

const read = file => JSON.parse(readFileSync(new URL(`../data/public/${file}`, import.meta.url)));
const guides = read("application_guides.json");
const routes = read("scholarships_2027.json").map(route => ({ ...route, applicationGuide: guides[route.id] }));
const overlays = read("overlay.example.json");

test("tracking has no cap and preserves undecided priorities and application decisions", () => {
  const selected = overlays.map((overlay, index) => ({ ...overlay, tracked: index < 12, applicationStatus: "NOT_STARTED" }));
  selected[7] = { ...selected[7], mainTarget: true, pursuitLevel: "FOCUS" };
  selected[3].pursuitLevel = "FOCUS";
  selected[2].pursuitLevel = "BACKUP";
  const before = JSON.stringify(selected);
  const result = trackedRoutes(routes, selected);
  assert.equal(result.length, 12);
  assert.equal(result[0].id, selected[7].routeId);
  assert.equal(result[1].id, selected[3].routeId);
  assert.equal(pursuitLevel(selected[0]), "UNSET");
  assert.equal(inMyCalendar(selected[2]), true, "backup dates are retained");
  assert.equal(JSON.stringify(selected), before);
});

test("reusable readiness never completes a scholarship step and progress is isolated per scholarship", () => {
  const route = routes.find(route => guideItems(route).some(item => item.sharedKey));
  const item = guideItems(route).find(item => item.sharedKey);
  const state = { tasks: {}, bricks: { [item.sharedKey]: true } };
  assert.equal(checklistProgress(route, state).done, 0);
  state.requirements = { [route.id]: { [item.id]: { status: "DONE" } } };
  assert.equal(checklistProgress(route, state).done, 1);
  assert.equal(checklistProgress(route, state, true).done, 1);
  assert.equal(checklistProgress({ ...route, id: "another-scholarship" }, state).done, 0);
  const next = guideItems(route).find(step => step.id !== item.id);
  state.requirements[route.id][next.id] = { status: "DOING" };
  assert.equal(checklistProgress(route, state).next.id, next.id);
});

test("only conditional steps can be omitted from totals and missing guides stay unknown", () => {
  const route = routes.find(route => guideItems(route).some(item => item.optional));
  const optional = guideItems(route).find(item => item.optional), required = guideItems(route).find(item => !item.optional);
  const state = { tasks: {}, bricks: {}, requirements: { [route.id]: { [optional.id]: { status: "NOT_NEEDED" }, [required.id]: { status: "NOT_NEEDED" } } } };
  const progress = checklistProgress(route, state);
  assert.equal(progress.total, guideItems(route).length - 1);
  assert.equal(progress.skipped, 1);
  assert.equal(progress.done, 0);
  const missing = checklistProgress({ ...route, applicationGuide: undefined }, state);
  assert.equal(missing.total, 0);
  assert.equal(missing.next, undefined);
});
