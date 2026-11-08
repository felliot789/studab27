# Handoff

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
