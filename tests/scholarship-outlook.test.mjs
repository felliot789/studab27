import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { matchesOutlook, outlookCategory, publishedAwardRate } from "../src/lib/scholarship-outlook.ts";

const catalogue = JSON.parse(readFileSync(new URL("../data/public/scholarships_2027.json", import.meta.url)));
const reviews = JSON.parse(readFileSync(new URL("../data/public/scholarship_outlooks.json", import.meta.url)));
const routes = catalogue.map(route => ({ ...route, scholarshipOutlook: reviews[route.id] }));
const routeNumber = n => routes.find(route => route.id.startsWith(`route-${n}-`));

test("outlook filtering excludes only the requested group and preserves unknowns and source data", () => {
  const before = JSON.stringify(routes);
  const all = routes.filter(route => matchesOutlook(route, "ALL"));
  const withoutLottery = routes.filter(route => matchesOutlook(route, "ALL", true));
  const lottery = routes.filter(route => matchesOutlook(route, "LOTTERY"));
  assert.equal(all.length, catalogue.length);
  assert.ok(lottery.length > 0);
  assert.equal(withoutLottery.length + lottery.length, all.length);
  assert.ok(withoutLottery.some(route => outlookCategory(route) === "UNKNOWN"));
  assert.ok(routes.filter(route => matchesOutlook(route, "REACH", true)).every(route => outlookCategory(route) === "REACH"));
  assert.equal(JSON.stringify(routes), before);
});

test("automatic funding, priority labels, and planning checks never imply a realistic overall path", () => {
  assert.equal(outlookCategory(routeNumber("30")), "UNKNOWN", "KAIST still needs admission evidence");
  assert.equal(outlookCategory(routeNumber("45")), "LOTTERY", "Harvard funding does not erase admission selectivity");
  assert.equal(outlookCategory({ ...catalogue[0], personalStrategyTier: "REALISTIC", budget: "PASS", sat: 1600 }), "UNKNOWN");
  assert.equal(outlookCategory({ ...catalogue[0], scholarshipOutlook: { category: "REALISTIC", reason: "Guess", reviewedAt: "2026-11-04", evidence: [] } }), "UNKNOWN");
});

test("award counts, admission rates, and shortlisted finalist counts never masquerade as award percentages", () => {
  for (const route of routes) assert.equal(publishedAwardRate(route), null);
  const sourceUrl = "https://scholarship.example/results";
  const review = { ...reviews[routeNumber("03").id], evidence: [{ url: sourceUrl }] };
  const rate = { outcome: "SCHOLARSHIP_AWARDED", applicantStage: "ALL_APPLICANTS", cycle: "2026 entry", population: "All eligible first-year award applicants", applicants: 200, recipients: 100, sourceUrl };
  const withRate = patch => ({ ...catalogue[0], scholarshipOutlook: { ...review, publishedRate: { ...rate, ...patch } } });
  assert.equal(publishedAwardRate(withRate({})), "50%");
  assert.equal(publishedAwardRate(withRate({ recipients: 0 })), "0%");
  assert.equal(publishedAwardRate(withRate({ recipients: 1, applicants: 100000 })), "<0.1%");
  for (const patch of [{ outcome: "ADMISSION" }, { outcome: "SCHOLARSHIP_FINALIST" }, { applicantStage: "FINALISTS" }, { applicants: 0 }, { recipients: 201 }, { applicants: -20 }, { recipients: 0.5 }, { cycle: "" }, { population: "" }, { sourceUrl: "https://unrelated.example/" }])
    assert.equal(publishedAwardRate(withRate(patch)), null);
});
