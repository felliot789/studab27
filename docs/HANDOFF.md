# Handoff

**Release reviewed: 2026-11-07 (Asia/Jakarta). Deployed: 2026-11-05 at 23:53 WIB.** This release builds on `e8ef249ec9ae747a60be91a9f1a74e481e0dd034` and packages the deployed scholarship descriptions, scoped Schola and adaptive research, plus earlier documentation/tooling and LAN access changes. Production build ID at deployment: `66WWdYP7v4cl5lbbGyJVT`. Use `git log -1 --oneline` for this release's commit and compare this dated snapshot with `git status --short --branch` before continuing. The release review does not restart or redeploy services.

## Resume here

Read [AGENTS.md](../AGENTS.md), [PRODUCT.md](../PRODUCT.md), [REPO_MAP.md](REPO_MAP.md), and the relevant [decisions](DECISIONS.md). [README.md](../README.md) owns setup and operations. Read only the source files needed for the next task. The local Graphify graph is optional navigation, not a prerequisite.

The documentation work adds this handoff, architecture map, decision records, startup/maintenance instructions, local-link checks, and a repeatable code-only graph command. LAN access uses a separate login through the `studab27-lan` nginx container and the loopback web service; the public HTTPS login remains separate. No scholarship choices were changed.

The current feature makes Description directly accessible from the catalogue and tracker, with a scholarship-specific Schola popup on each detail page. General Schola remains separate. Route-scoped history, tools, profile/plan/checklist context and browser-tab drafts are isolated. The same configured model, daily call budget and serial worker serve all conversations. Closing a popup preserves drafts/jobs; explicit retry preserves an unrelated draft.

Schola now uses LangGraph 1.2.20 through `.venv-research` with the existing budgeted transport and restricted tools. Production selects `llm.researchRuntime=langgraph` and native function calling for the configured `vc/claude-sonnet-4-6` alias. Research supports iterative discovery, ordinary official-link navigation, text PDFs, phrase-focused excerpts and continuation offsets. Findings and dated source provenance persist in the selected conversation. The full Local Deep Research package is not installed; see decision 11. No autonomous journey management, new paid search service or cloud connection was added.

A dedicated pinned SearXNG container, `studab27-research-search`, listens only at `127.0.0.1:8081` and restarts unless stopped. Its free Brave/DuckDuckGo engines returned useful official scholarship results. The earlier SearXNG service remains unchanged. Search settings and deployment metadata are under the ignored `private/research-search/`; the canonical Schola configuration points at the dedicated service. Rollback build, configuration, unit and consistent SQLite backup are under `private/deployments/20261105T165311Z/`.

## What is implemented at the application baseline

| Area | Current behavior |
| --- | --- |
| Tracker | Home and Scholarships show chosen routes with no tracking cap. Priority, main target, and application progress are explicit, separate controls. |
| Scholarship guides | Permanent detail pages open on source-scoped checklists; catalogue links open Description. Five public guides contain 64 steps. Routes without guides show that limitation. |
| Documents | Scholarship-specific document progress shares state with checklists; reusable packs are separate readiness hints. |
| Catalogue and outlook | 57 public routes; Realistic/Reach/Lottery/Unknown assessments and explanations. The initial evidence establishes no published award rate or Realistic classification. |
| Calendar | 174 records in the reviewed public dataset: 80 with target-cycle date support and 94 pending/conflicting. Default scope includes tracked, saved, and active routes. |
| UI | Quiet dark layout, mobile navigation, styled selectors with a native fallback, and small country flags with text labels. |
| Schola and monitoring | General research chat plus isolated scholarship consultants, bounded adaptive research, durable jobs/provenance, conservative evaluation, at most three briefing tasks, separate source snapshots/diffs, local exports, and protected runtime access. |

Personal selections, priorities, notes, and progress live only in the local vault. A clone gets fictional examples; the graph and these docs cannot reconstruct the owner's workspace. Existing private state must be preserved during any development or deployment.

## Verification for this handoff change

Update this table with results actually observed, rather than carrying forward earlier claims.

| Check | Result |
| --- | --- |
| `npm run check` | Passed again on 2026-11-07: TypeScript, Python suite (45 discovered, six optional-runtime checks skipped in system Python), 11 Node tests, public-data validation, and documentation targets. The release scans the 31 staged source/docs/test files with the privacy hook and compares staged blobs against configured secrets before commit. The earlier deployment also checked 433 staged-build text files against configured secrets; no matches. |
| Research environment | All 45 Python tests passed again on 2026-11-07 without skips under `.venv-research`, with resource warnings treated as errors. `pip check` passed. Tests include actual graph → scoped SQLite tools → saved provenance, serial multi-tool order, original-thread callbacks and disabled ambient remote tracing. Independent code and publication reviews found no material blocker. |
| `npm run map` | Rebuilt after research changes with Graphify 0.9.28: 502 nodes, 1,083 relationships, 34 communities; zero model calls. |
| Production build / HTTP checks | Isolated production build and 400-file public-build privacy scan passed. HTTP fixtures covered all 57 scholarship pages, scoped/general queue separation, idempotency, invalid/cross-scope IDs and LAN/public login/session protections. Production also returned 57 routes and 174 calendar records after deployment. |
| Browser | Earlier fictional UI checks on the same frontend passed on desktop and at 320×640, 390×844 and 768×1024: Description, isolated drafts/history, close/reopen, queue/retry, contained scrolling, composer and Escape focus restoration. A fresh follow-up preview attempt was blocked by the desktop browser client; it added no browser validation. No browser-triggered model calls or real-phone keyboard test. |
| Live inference / research | 13 model calls: native contract probe; complete KAIST and UBC research runs (four calls each); deadline follow-up (three); final date-classification check (one). Real public discovery, official reads, useful follow-up links and saved provenance worked. Live HKU text-PDF reading passed without a model call. KAIST reads timed out intermittently; initial research recovered, while a later follow-up explicitly disclosed failed fresh reads. An observed closed/upcoming-window advice error led to explicit date instructions; the final bounded classification check was correct. Model prose remains fallible evidence. Fictional context only in validation. |
| Services / remote access | Waited for no active jobs; deployed the updated worker/runtime before exposing the new web build. Web and Schola active/running, fresh heartbeat, timer active/waiting, app loopback listener retained. Authenticated and unauthenticated checks passed through LAN and HTTPS ports 9443/10000; LAN rejects the public session. Four existing private plan/profile/state files matched their pre-deployment hashes; conversation history retained. Physical LAN-client and phone validation remain outstanding. |
| Repository publication | On 2026-11-07, verified `origin` targets the intended private GitHub repository; default branch `main` was at the parent baseline above and the existing cloud Watchtower workflow was `disabled_manually`. Publish this release on `codex/repo-handoff`; committing/pushing does not enable the workflow or change repository visibility. Verify its remote SHA after push. |

## Known limits and next-task boundaries

- Only five routes have researched application guides; other routes remain trackable without invented default requirements. Public source assessments are dated research, not verified personal eligibility or calibrated odds.
- Styled selector appearance varies by browser. Responsive browser checks do not prove behavior on a physical phone or its keyboard.
- One web process serializes JSON mutations; multiple server workers need transactional storage. Backups do not include original supporting files, chat SQLite, or model/access configuration; see [README.md](../README.md#private-data-and-demo-mode).
- Google Drive and Calendar are not connected. Search can degrade even when its HTTP request succeeds. No new cloud connection, notifications, automatic decisions, or application submission is implied.
- Future deployments must wait for active jobs and start the scope-aware worker before exposing scoped sends. The deployed store has additive `job_scopes` and message/tool scope fields; old general-write SQL stays compatible, but an old worker cannot interpret specialist scope. The worker unit now uses `.venv-research/bin/python`; rebuilding that environment requires `requirements-research.txt` and its checks.
- Research reads HTML and text PDFs only: no JavaScript rendering, OCR, authenticated portals or CAPTCHA bypass. Free search availability varies; test real queries after engine updates. Four distinct searches, twelve tools and configured model rounds bound each job. The ten-minute budget is checked between operations; an in-flight request retains its own timeout. Evidence access does not guarantee correct model interpretation or current-cycle eligibility.
- A code-only graph misses framework routing, runtime JSON joins, subprocess boundaries, and intent. The extraction skips CSS and can omit data or empty files. Relationships include structural inferences; a shortest path through shared imports is not proof of a runtime call chain. Confirm findings in source and the [documented flows](REPO_MAP.md).

## Continue safely

1. Inspect the working tree and changes since the baseline. Preserve unrelated work and the vault. Use demo mode for reversible UI/data experiments.
2. Follow the map to the implementation and tests. Read the installed Next.js guide before app code changes, as required by AGENTS.md.
3. Run `npm run check`. For app changes, also build and run the relevant production checks from README. If production is running, use a separate staging checkout so its `.next` stays intact.
4. Before a planned restart, inspect active Schola jobs and wait for them to finish. Verify application health after deployment; a successful service command alone is insufficient.
5. Update the map for changed flows, decisions for changed choices, and this file with the baseline, remaining work, and observed validation. Rebuild the optional graph after code changes.

Keep this file short and current. Git history holds the detailed chronology; a handoff should describe the state the next harness will actually encounter.
