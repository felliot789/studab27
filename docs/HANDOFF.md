# Handoff

## Personal-use purpose — 2026-11-16

Baseline: `9f02295`. README and PRODUCT headers now explicitly state that StudAb27 supports the owner's personal scholarship journey, with no marketing, sales, or monetization goals. The owner is the sole intended user. Development priorities follow personal usefulness, privacy, reliability, and manageable upkeep.

This is a documentation-only clarification. No runtime deployment is required; the existing implementation, validation limits, and remaining work below still apply.

Validation: `npm run check` passed (124 Python tests with 11 optional-runtime skips; 22 Node tests, TypeScript, public data, and documentation-link checks). The documentation diff received a read-only review.

## Schola research status clarity — 2026-11-16

Implementation baseline: `db5269e`. Deployed web build: `-t6Mu4Ur6Xjl3n2AFsBFP`. A completed failed tool step previously appeared directly under Processing request, making a continuing job look stalled. Every tool exception also left the same generic stored summary, so earlier failures cannot be diagnosed retrospectively from that row alone.

The running status now labels the latest completed step as **Last research step**, with the background-processing notice in a separate paragraph. Queued jobs show a waiting state. Tool timestamps must belong to the current RUNNING attempt, so explicit retries do not display stale failure summaries from an earlier attempt. Missing timestamps use a neutral progress message. Drafts, sending, scope and polling keep their existing behavior.

New failed steps persist only safe reason categories, including exact source HTTP status, timeouts, TLS/address/connection failures, unavailable source links, rejected arguments and PDF extraction limits. Summaries contain no raw exception body, source URL, arguments or credentials. The existing sanitized model tool-result error, source provenance, budgets and explicit-retry behavior remain unchanged. No old tool rows or answers were rewritten, and this release does not establish the causes of the earlier failed reads or make unavailable websites accessible.

Validation: isolated `npm ci`, `npm run check` (124 Python tests with 11 optional-runtime skips; 22 Node tests), production build, emitted-build privacy review (457 text files) and fictional HTTP checks passed. All 124 Python tests also passed without skips in the actual research environment with the pinned SQLite runtime and ResourceWarnings treated as errors. The regression covers a failed HTTP 403 read followed by successful synthesis, one fetch without an automatic retry, a DONE job, preserved UNKNOWN and no source attribution or plan mutation. Safe-summary checks include secret-bearing exception text and malformed HTTP messages. A read-only diff review found no actionable issues.

Browser fixtures verified a current HTTP failure, queued retry, a new running attempt with stale old tools hidden, and a later timeout summary. Desktop and 320px viewport checks showed no overflow or browser errors; no model request or real conversation was used as a test. The ignored code-only graph was rebuilt without model calls.

Deployment waited for zero active jobs and an idle scan, switched the tested web build and reloaded the idle worker. Workspace/conversation/job/call records, configuration and source-monitor fingerprints matched before and after; authenticated dashboard values matched, unauthenticated APIs remained 401, both stores and verified local recovery were healthy, and both timers remained active. The prior build and assistant source remain in the ignored deployment vault for rollback. No schema, model setting or access-control change was needed.

## UI navigation performance — 2026-11-16

Implementation baseline: `bc99395`. Deployed web build: `rJahPZ8_dyfaWWsdxgnmN`. Page switching and opening scholarships were the reported slow paths. The existing Next.js/React UI and Python/SQLite storage remain in place.

Pages and scoped dashboard refreshes now serialize the records required by their view. Scholarship pages retain the complete selected route, guide, plan, evaluation, shared readiness, source notes, dates and direct calendar prerequisites, including hidden tabs. Tracker and Documents retain tracked routes. Calendar retains the full selectable route/date inventory. Storage, revision checks, exports and the default full dashboard API keep their contracts; projection never writes back a partial snapshot. Duplicate local-route/draft stores stay on the server, with their existing review API still available.

Secondary screen code and the scholarship chat popup load on demand with server rendering enabled. Dashboard derivation combines task-pool generation, evaluations and briefing in one Python invocation, reducing a dashboard load from four Python processes to two; ordinary mutations skip unused pool generation. Date formatters are reused, catalogue joins are indexed, and unchanged chat text is not reparsed while typing. Internal document-pack links use client navigation.

A paired, alternating 20-sample loopback comparison used separate production builds, the same 68 public routes/200 events and three tracked fictional guided routes, with matched explicit fixture actions and no model requests. Times measure complete HTTP response reads, not browser interaction latency or phone network performance.

| Measure | Before | After |
| --- | --- | --- |
| Tracker HTML response median | 168.0 ms | 85.2 ms |
| Scholarship HTML response median | 166.5 ms | 86.3 ms |
| Save plus Documents refresh median | 291.1 ms | 186.5 ms |
| Tracker HTML body | 965,107 bytes | 52,014 bytes |
| Scholarship HTML body | 996,035 bytes | 66,092 bytes |
| Scholarship HTML gzip estimate | 92,067 bytes | 12,481 bytes |
| Scoped scholarship dashboard JSON | 880,232 bytes | 12,316 bytes |

Tracker initial script bodies decreased from 723,976 to 638,684 raw bytes (221,793 to 199,351 bytes with per-file gzip estimates). HTML and JSON figures are from the paired run; script figures are from separate cold-route asset inventories. Gzip figures are local compression estimates, not measured network transfer counts. These are fixture-specific measurements, not a promise of a fixed speedup on every device.

Validation: isolated `npm ci`, `npm run check` (122 Python tests, 11 optional-runtime skips; 22 Node tests), production build, emitted-build privacy review (457 text files) and fictional HTTP checks passed. HTTP coverage includes all 68 public scholarship pages, scoped responses and cross-route calendar prerequisites, progress persistence, local additions, conflicts, export/import, sessions, exact origins and CSRF. Browser checks covered desktop and 320/390px viewports: tracker/detail/Documents/Calendar switching, hidden detail tabs, a saved checklist change, reusable documents, All routes, and closing/reopening an unsent scholarship-chat draft. No horizontal overflow or browser errors were observed. A read-only diff review found no actionable regressions; the ignored code-only graph was rebuilt without model calls.

Deployment waited for zero active Schola jobs and an idle scan, then switched only the tested web build. Workspace/conversation records and configuration/monitor fingerprints matched before and after; full authenticated dashboard values also matched. Scoped private reads returned 200, unauthenticated API access remained 401, both stores and verified local recovery were healthy, both timers stayed active, and the worker PID was unchanged. The previous build and source checkpoint remain in the ignored deployment vault for rollback. No database migration, worker restart or model request was needed.

Remaining limits: physical-phone and real-network interaction timings were not measured. The shell still mounts per page, and Catalogue/Calendar intentionally retain their full selectable records. If navigation remains slow on the target phone, profile that device/network before expanding the architecture or changing languages.

## Reviewable local scholarship additions — 2026-11-16

Implementation baseline: `800348d`. Deployed build: `1YiYhJMqiu-gqH3TvKoLB`. Explore and general Schola now offer **Add new scholarship**: public research request → durable draft → review/edit → explicit **Add to Explore**. Drafts and accepted additions live in the canonical workspace state and survive workspace export/import, offline mirror and full local recovery. Accepted entries remain local, untracked and outside Git; they create no confirmed dates, researched guide, priority or eligibility rule. Exact institution/award duplicates return the existing entry; institution variants and shared source URLs also warn about possible matches without merging distinct awards. See [draft review](../src/components/scholarship-drafts.tsx), [catalogue store](../schola/catalogue.py) and [decision 13](DECISIONS.md#13-schola-proposes-explicit-acceptance-adds-to-the-local-catalogue).

Only explicitly requested draft jobs receive a proposal tool. Source URLs must have been fetched in that job; retrieval timestamps come from the server. Draft research omits owner profile and conversation memory. Ordinary chat and background tools remain read-only. The final model reply and actual tool slot are reserved for draft persistence; oversized batches receive bounded skipped-call results rather than losing final synthesis. Exact user/search/fetched public candidates can be read without claiming that their domain or contents establish authority. Private links, credentials and invented paths remain blocked.

Validation passed `npm run check`: 121 Python tests (11 optional-runtime skips with system Python), 17 Node tests, TypeScript, public data and documentation checks. All 121 Python tests also passed under the research interpreter with the pinned SQLite runtime, without skips. A separate staging checkout passed dependency installation, production build, emitted-build privacy review (415 text files), and fictional HTTP checks covering all 68 public pages plus local additions, conflicts, repeat acceptance, export/import recovery and access controls. Browser checks covered 320, 390, 768 and 1280px without horizontal overflow; closing/reopening preserved unsaved fields and restored focus. Explicit acceptance immediately refreshed Explore and opened the permanent local page; no console errors were observed. These are browser viewport checks, not physical-phone evidence.

Focused live Hydrogen checks used 19 inference calls in isolated fictional workspaces. Both actual draft/accept/restore runs succeeded; the final run preserved 20% tuition, SMA equivalence and unstated ancillary support as UNKNOWN where appropriate. The two-award comparison passed on an explicit follow-up after an earlier empty provider completion. That failure remains recorded; Schola rejected it rather than fabricating an answer. Search degradation and occasional empty proxy responses remain operational limits. Provider alias/xhigh semantics were not independently attested. Raw audit artifacts remain ignored and were not published.

Deployment waited for zero active jobs, paused writers and the watcher timer, created verified pre/post snapshots and switched the tested build with the compatible worker. Only `llm.model` changed in local configuration, to `clipa/gemini-4-hydrogen-xhigh`; other settings matched. Workspace, conversation/job/call records and supporting-file fingerprints matched before/after. Authenticated dashboard/chat/export/draft APIs and new UI entry points passed; unauthenticated APIs remained 401. An isolated restore of the post-release snapshot matched the workspace. Both stores use SQLite 3.54.1, web/worker are active and the watcher schedule resumed. The first deployment attempt automatically rolled back because its restore-drill destination was inside the checkout; the corrected outside-checkout drill and repeated deployment passed. The previous build and snapshots remain in the ignored vault. No owner scholarship was added as a test. Off-device recovery remains deferred.

Remaining limits: drafts require human evidence review; no automatic application checklist or calendar creation, publication to the public catalogue, application submission or tracking occurs. Accepted entries cannot yet be edited through the draft form. Research limits can leave a preserved lead requiring explicit retry or manual editing.

## Recovery storage cleanup — 2026-11-15

Baseline: `025066b`. Recovery now excludes the exact vault-root `releases` and `lan-previous-build` operational directories, which previously copied old builds and caches into every data snapshot. Identically named nested supporting-document folders remain included. Existing recovery tests cover both boundaries; [DATABASE.md](DATABASE.md) records the exclusions.

A new lean snapshot passed full verification and an isolated restore drill: all 224 files, both logical database copies and the pinned SQLite runtime matched. Before pruning nine build-heavy snapshots, every non-build payload and original manifest was preserved in a private compressed history archive and checked against a separate hash inventory. This archive preserves historical data; it is not a complete snapshot accepted by the recovery CLI. The full migration checkpoint and its paired build, the fresh native snapshot, the latest compatible rollback source/build and small historical bundle metadata remain available. Ten obsolete build directories were removed. Local cleanup inventories and archive details remain in the ignored vault.

Disk usage fell from about 4.9 GiB to 1.0 GiB. The current production build, dependencies and research environment were retained. Owner workspace/conversation records, eligible supporting-file hashes and configuration matched the pre-cleanup baseline. Authenticated tracker/dashboard/chat checks passed, unauthenticated API access remained 401, both stores and local recovery were healthy, and the web/worker PIDs stayed unchanged during cleanup. Both daily timers remain enabled; the normal 14-snapshot retention policy is unchanged.

Validation passed `npm run check` under the research Python environment with the pinned SQLite library: 86 Python tests, 17 Node tests, TypeScript, public-data and documentation checks. The 15-test recovery suite also passed separately. The code-only local graph was rebuilt without model calls. No Next build, web/worker restart, migration or live model request was needed. Off-device recovery remains deferred.

## Engineering/CS research catalogue — 2026-11-15

Baseline: `6e0ad4c`. A second returned research report provided literal official URLs after the first run's separate data files could not be retrieved. The report was treated as a discovery index, and official sources were independently checked before updating public facts. The lost research JSON was not recovered.

The catalogue now has 68 routes: all 57 original IDs are retained, all 18 original US routes have scoped review updates, and 11 new routes cover four US mechanisms, five Australian awards, one Swedish award and Beasiswa Garuda as a separate Indonesian sponsor. No host pairing is implied for Garuda. There are 200 calendar records (102 target-cycle-supported, 98 unscheduled) and 31 guides (26 added). See the [research checkpoint](RESEARCH-2026-11-15.md) for funding gaps, exclusions and unresolved eligibility evidence. Existing combined university pages retain their identities and saved plans; new entries start unset.

Catalogue projection, validation, tests and fictional HTTP checks now derive inventory from the actual definitions instead of freezing the old 57/174 counts. Reviewed projection records require an explicit review date. The historical private seed-bootstrap script still describes its original fixed-format input; it is not a current catalogue importer.

Validation in an isolated checkout passed the production build, emitted-build privacy scan (404 text files), `npm run check` (86 Python tests with six optional-runtime skips, 17 Node tests), public-data validation and 68-page fictional HTTP checks covering tracking, guides, persistence, recovery and access controls. An old calendar fixture count failed first; replacing that frozen count with the pending-date invariant passed the full check. No actual applicant eligibility or live model result was used as test evidence.

The data-only update was applied after zero queued/running research jobs. The existing server reads these public definitions at request time; the served `.next` output was not rebuilt and web/worker PIDs stayed unchanged. Workspace database/configuration and message/job fingerprints matched before and after. Live unauthenticated API access remained 401. No owner plan, priority, checklist completion, source-monitor baseline or cloud connection was imported from the report. Authenticated live browser flows were not rechecked; the HTTP flow checks used an isolated fictional workspace.

Remaining work: programme-level Indonesian diploma/graduation timing, ancillary cost/cashflow and renewal details where unresolved, Garuda's exact approved-host mapping, Miami Stamps access and current Trustee-specific availability. General annual dates remain unscheduled rather than receiving guessed years or cutoffs. Local recovery remains governed by [DATABASE.md](DATABASE.md); this update does not establish off-device recovery.

## Objective interface copy — 2026-11-09

Baseline: `ea31373`. Deployed build: `pzP3gtWiLI7rW0DV5gBZa`. Removed the sidebar subtitle, private workspace footer, and sign-in taglines. Page titles, tabs, instructions, empty states, notifications, Schola suggestions, and future worker status/error messages now use objective wording. Checklist guides, reusable document packs, and generated task descriptions use the same tone. Practical privacy disclosures, restore consent, evidence limits, and the fictional-demo indicator remain. [PRODUCT.md](../PRODUCT.md#brand-personality) records the copy convention. No schema, source URL, requirement ID, or stored owner record changed.

The isolated checkout passed `npm ci`, `npm run check` (86 Python tests, six optional-runtime skips; 17 Node tests), production build, emitted-build privacy review, and fictional HTTP checks. Browser verification covered 15 pages at 320, 390, and 1280px: 45 page/viewport checks with no horizontal overflow, direct reader address, or browser errors. Mobile tools, vault, and scholarship Schola dialogs worked; tools restored keyboard focus. Screenshots of tracker and sign-in layouts were visually reviewed. These are browser viewport checks, not physical-phone evidence. Public JSON structure/source URLs and string-only Python changes were checked; the local code-only graph was rebuilt without model calls.

Deployment waited for zero active Schola jobs, switched only the tested web build, and reloaded the idle worker for its changed status strings. Workspace, conversation/job records, configuration, and existing worker-error metadata matched their pre-switch fingerprints; both timers remained active. Authenticated pages/dashboard/chat/export passed, unauthenticated API access remained 401, both stores were healthy, and local recovery remained verified. The initial verification helper used an incorrect recovery-health field name and automatically restored the old build; correcting that helper and repeating the switch passed all checks. Rollback builds remain in the ignored deployment vault. No live model request or historical conversation rewrite was used.

## Narrow mobile logo correction — 2026-11-09

Baseline: `0fef7d5`. Deployed build: `lTccU59g1Ngk2Avd5JUWY`. The earlier text fallback below 390px still displayed the old wordmark on the tracker. The mobile header now uses the supplied logo at every phone width, shrinking within the available space while keeping its controls intact. The logo asset, desktop sidebar and sign-in branding are unchanged. See [Workspace](../src/components/workspace.tsx) and [responsive styles](../src/app/redesign.css).

The isolated checkout passed `npm ci`, `npm run check` (86 Python tests, six optional-runtime skips; 17 Node tests), production build, emitted-build privacy review and fictional HTTP checks. Browser checks covered 320, 360, 375, 389, 390, 430, 768, 900, 901 and 1280px. The mobile logo remained visible, header controls stayed within the viewport without overlap, both tracker URLs worked, and the mobile tools opened and closed with focus restored. These are viewport checks, not physical-phone evidence. The code-only graph was rebuilt locally.

The tested web build was switched after zero active jobs. Live authenticated `/` and `/scholarships` returned the supplied logo without the old mobile wordmark. Workspace/configuration fingerprints and the worker PID were preserved; the unauthenticated logo loaded and API access remained 401. The previous build is retained under the ignored deployment vault. No worker restart, data migration or model request was needed.

## Header branding update — 2026-11-08

Implementation baseline: `568bbfd`. Deployed production build: `Yz_yz_ltzda6Uy1rg1_lp`. The supplied logo is embedded unchanged in a local SVG viewport that trims its empty margins. The sidebar and sign-in screen use the full logo; mobile headers show it from 390px, with compact text below that width. Narrow headers retain labeled, touch-sized Schola/tools controls. See [Workspace](../src/components/workspace.tsx), [Login](../src/app/login/page.tsx), [logo asset](../src/assets/studab27-logo.svg), and [responsive styles](../src/app/redesign.css).

Validation: a separate checkout passed `npm ci`, `npm run check` (86 Python tests, six optional-runtime skips; 17 Node tests), production build, emitted-build privacy review and the fictional HTTP checks. Browser previews checked 320, 375, 390, 430, 768, 1024 and the default 1280px desktop layout; header bounds did not overlap or overflow. Sign-in was reviewed at 320px and desktop, and mobile tools opened and closed with focus restored. These are browser viewport checks, not a physical-phone test. The code-only local graph was rebuilt without model calls.

Deployment switched only the tested web build after zero active jobs. Protected workspace fingerprints and configuration matched before/after, the worker PID stayed unchanged, login and the unauthenticated static logo returned 200, and unauthenticated API access remained 401. Both stores and local recovery remain healthy. The previous build is retained under the ignored deployment vault for rollback; this change requires no database migration.

## Database reliability baseline

**Database reliability release deployed: 2026-11-07 23:51 WIB. Code checkpoint: `5d1fcd2055892129bfb4e15d3672a5f7376fd872`; prior baseline: `e707179ebe80057bb6e7efdc8428f778c1a8afd4`.** Production build: `arBO0Kidm4QYZMcRsAIGv`. Check `git status --short --branch` and `git log -1 --oneline` before editing; a later documentation-only commit records these results.

## Resume here

Read [AGENTS.md](../AGENTS.md), [PRODUCT.md](../PRODUCT.md), [REPO_MAP.md](REPO_MAP.md), [DECISIONS.md](DECISIONS.md) and [DATABASE.md](DATABASE.md). The database guide owns migration, full local recovery, isolated restore and coordinated rollback procedures. [README.md](../README.md) owns normal setup and service operations.

## Implemented

- Private profile, route plans, milestones, inbox, task/document/checklist progress now live in entity tables in `private/workspace.sqlite3`. Legacy JSON is imported once and preserved unchanged; it stops being a live input after PRIVATE initialization. Dashboard, exports, Schola context and offline mirror use committed snapshots.
- Whole-workspace transactions and revision/mode checks prevent partial imports and lost concurrent writes. Conflicts return HTTP 409. Retired identifiers, unknown fields and old checklist records remain recoverable; interactive changes still validate current definitions. Required steps with a historical skip are shown for recheck, and note-only edits preserve their prior progress.
- Workspace and conversation schema versions, foreign keys, state constraints, scope triggers, indexes and pre-migration copies protect data. Missing historical job references receive archived placeholders without changing original message/tool records. Retry receipts prevent delayed/repeated requests from requeueing completed replies.
- App-only SQLite 3.54.1 is pinned to official archive/source hashes and attested under the actual Python interpreters. Runtime wrappers supply it to the web API, worker, watcher and recovery service. Production launchers require it; system libraries remain unchanged.
- Complete local recovery snapshots include both online database copies, eligible vault/configuration/original files, monitor baselines, public definitions and runtime/version files. Hashes, SQLite integrity, references and permissions are verified before publication. Restore requires a new isolated directory. Retention keeps the latest 14 verified copies and preserves invalid/foreign copies.
- The recovery timer is enabled for daily 03:17 WIB plus up to ten minutes of delay, with persistent catch-up. The actual service completed successfully and its output passed an isolated restore drill. Health verifies the newest snapshot and reports stale recovery after 48 hours. Workspace JSON exports remain separate from full recovery snapshots.
- Public catalogue, guides, calendar, owner decisions and Schola research boundaries retain their existing responsibilities. No cloud service, application submission, automatic plan decision or model request was added.

## Checks actually observed

| Check | Result |
| --- | --- |
| `npm run check` | Passed: TypeScript, 86 discovered Python tests (six optional-runtime skips in system Python), 17 Node tests, public data and documentation links. |
| Research/runtime environment | All 86 Python tests passed under the patched runtime with ResourceWarnings treated as errors; package dependency check passed. Both API/system Python and research Python attested SQLite 3.54.1/source identity. The live worker maps the pinned library, and the actual web process environment/binary reproduces that version for API children. |
| Isolated build / privacy / HTTP | Production build passed in a separate checkout. 400 emitted text files and private tracing checks passed. Fictional HTTP checks passed all 57 scholarship pages, persistence, export/import, scoped chat, sessions, exact origins, CSRF and LAN/public isolation. |
| Failure and concurrency checks | Actual TypeScript handlers and Python stores cover large legal exports, impossible dates, future schemas, unknown/retired records, concurrent revision conflicts, coherent export during a partial transaction, interrupted process rollback, retry races, read/write concurrency and demo isolation. |
| Complete recovery | Fixture tests cover WAL inclusion, tamper/corruption, unsafe paths, changing supporting files, retention and isolated restore. A full private copy of the real vault was restored and migrated separately; logical workspace and original conversation records matched exactly. No inference was run. |
| Graph | Code-only local graph rebuilt after implementation with zero model calls. Treat it as navigation and verify source; it omits runtime joins and public data content. |
| Publication | Release branch: `codex/database-reliability` on the existing private `origin`. The privacy hook reviewed all 37 implementation files; a local comparison against six configured secrets found zero matches. Completed, verified accomplishments must be committed and pushed with staged-content review and remote-commit verification, as recorded in [AGENTS.md](../AGENTS.md). |

## Observed deployment

Final deployment waited for zero queued/running jobs and no active scan, paused the old web/worker writers and watcher timer, and created a verified complete pre-migration snapshot. The tested source/build and attested app-only runtime were switched together. Both schema migrations passed; logical owner workspace and all original chat records matched their pre-migration fingerprints, and preserved legacy/configuration/source-monitor files were unchanged. The former dangling historical job reference is represented by an archived placeholder; original messages/tools remain intact.

The installed recovery service created a verified post-migration snapshot containing both canonical databases and eligible files. Its isolated restore matched workspace/conversation data, and the restored runtime was attested. The compatible worker started before the web app; the watcher schedule resumed, and the daily recovery timer was enabled. Web/worker are active, both timers wait, recovery service completed successfully, and maintenance reports both stores/recovery OK with a fresh worker heartbeat.

A fresh health check on 2026-11-08 10:48 WIB found both stores OK, SQLite 3.54.1, a healthy worker with zero active jobs, and the newest local recovery copy verified. That copy was created by the scheduled overnight run, confirming the daily backup operated after deployment. Off-device recovery remains unverified.

Protected dashboard/export/chat checks passed. The application returned 57 public routes and 174 public calendar records, unauthenticated API access returned 401, LAN/public sessions remained separate, and both configured HTTPS origins passed authenticated/unauthenticated checks. The application stays loopback-bound behind its existing proxies; no credentials or unrelated routes changed. No live inference was used for these checks.

Rollback source/build/unit copies, migration baselines and complete pre/post snapshots remain under the ignored vault. Use the coordinated procedure in [DATABASE.md](DATABASE.md); do not switch only code or delete active locks. Neither a successful build nor a service start replaces the preservation and recovery checks above.

## Known limits

- The user selected local recovery first. Snapshots are plaintext and protected by private permissions. Off-device storage and encryption are deferred; copies on this host do not protect against losing the host.
- A recovery copy is data plus version/runtime metadata and the installed private runtime. A compatible source checkout, dependencies and production build still need installation. Rollback requires a compatible source/build/data set, including any old legacy JSON inputs; switching only code can revive stale data.
- Original private JSON should not be edited as current state after migration. Keep migration copies and complete snapshots; never force a new schema onto an old worker.
- Physical phone/LAN-client behavior and browser visual revalidation were not repeated for this infrastructure release. Existing LAN HTTP remains unencrypted by owner choice; exact protected HTTPS access remains available.
- Guides still cover five public routes; research/eligibility uncertainty and the earlier product limits remain. Source evidence and model answers do not establish personal eligibility or award odds.
