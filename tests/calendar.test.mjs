import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { activeApplication, dateLabel, eventClock, eventDay, inMyCalendar, todayWib, upcomingEvents } from "../src/lib/calendar.ts";

const events = JSON.parse(readFileSync(new URL("../data/public/calendar_events.json", import.meta.url)));
const overlays = JSON.parse(readFileSync(new URL("../data/public/overlay.example.json", import.meta.url)));
const supported = events.find(e => e.calendarDateSupported);

test("unconfirmed and conflicting research never occupies a calendar day", () => {
  const pending = events.filter(e => !e.calendarDateSupported);
  assert.ok(pending.length > 0);
  for (const event of pending) assert.equal(eventDay(event), null);
  assert.equal(eventDay({ ...supported, sourceReview: { status: "CONFLICTING_OFFICIAL_SOURCES" } }), null);
  const mit = events.find(e => /MIT/.test(e.title) && e.candidateDate === "2027-01-04");
  assert.ok(mit);
  assert.equal(eventDay(mit), null);
});

test("published fixed time zones cross the WIB day without inventing date-only cutoffs", () => {
  const ubc = events.find(e => /UBC/.test(e.title) && e.date === "2026-11-15" && e.time);
  assert.equal(ubc.deadlineAtWib, "2026-11-16T14:59:00+07:00");
  assert.equal(eventDay(ubc), "2026-11-16");
  assert.equal(eventClock(ubc), "14:59 WIB");
  const dateOnly = events.find(e => e.calendarDateSupported && !e.time && !e.cutoffTimeText);
  assert.equal(eventDay(dateOnly), dateOnly.date);
  assert.equal(eventClock(dateOnly), "Cutoff time not published");
  assert.equal(todayWib(new Date("2026-11-03T18:00:00Z")), "2026-11-04");
});

test("reused date formatters preserve date-only labels and follow the WIB day boundary", () => {
  assert.equal(dateLabel("2026-11-03"), "3 Nov");
  assert.equal(dateLabel("2026-11-03", true), "3 Nov 2026");
  assert.equal(dateLabel("2026-11-03"), "3 Nov");
  assert.equal(todayWib(new Date("2026-11-03T16:59:59Z")), "2026-11-03");
  assert.equal(todayWib(new Date("2026-11-03T17:00:00Z")), "2026-11-04");
});

test("saved and active calendar scope preserves explicit application decisions", () => {
  const base = { ...overlays[0], applicationStatus: "NOT_STARTED", saved: false };
  assert.equal(inMyCalendar(base), false);
  assert.equal(activeApplication({ ...base, saved: true }), false);
  assert.equal(inMyCalendar({ ...base, saved: true }), true);
  for (const applicationStatus of ["RESEARCHING", "IN_PROGRESS", "SUBMITTED", "DEFER_TO_MAIN_ROUND"])
    assert.equal(inMyCalendar({ ...base, applicationStatus }), true);
  assert.equal(inMyCalendar({ ...base, applicationStatus: "DROP" }), false);
  const unchanged = JSON.stringify(overlays);
  const noSelection = overlays.map(o => ({ ...o, saved: false, applicationStatus: "NOT_STARTED" }));
  assert.equal(upcomingEvents(events, noSelection, false, new Date("2026-11-03T00:00:00Z")).length, 0);
  assert.ok(upcomingEvents(events, noSelection, true, new Date("2026-11-03T00:00:00Z")).length > 0);
  assert.equal(JSON.stringify(overlays), unchanged);
});

test("interview ranges remain upcoming through their final day", () => {
  const range = events.find(e => e.endDate === "2027-03-23");
  assert.ok(range);
  assert.equal(upcomingEvents([range], [], true, new Date("2027-03-22T00:00:00Z")).length, 1);
  assert.equal(upcomingEvents([range], [], true, new Date("2027-03-24T00:00:00Z")).length, 0);
});

test("an elapsed exact cutoff is not offered as an upcoming deadline", () => {
  const exact = { ...supported, date: "2026-11-03", endDate: undefined, deadlineAtWib: "2026-11-03T09:00:00+07:00" };
  assert.equal(upcomingEvents([exact], [], true, new Date("2026-11-03T01:59:00Z")).length, 1);
  assert.equal(upcomingEvents([exact], [], true, new Date("2026-11-03T02:01:00Z")).length, 0);
});
