# Handoff

**Database reliability release prepared: 2026-11-07 (Asia/Jakarta). Baseline: `e707179ebe80057bb6e7efdc8428f778c1a8afd4`.** Check `git status --short --branch` and `git log -1 --oneline` before editing. This preparation checkpoint has passed staging validation; the live migration is the next controlled step.

## Resume here

Read [AGENTS.md](../AGENTS.md), [PRODUCT.md](../PRODUCT.md), [REPO_MAP.md](REPO_MAP.md), [DECISIONS.md](DECISIONS.md) and [DATABASE.md](DATABASE.md). The database guide owns migration, full local recovery, isolated restore and coordinated rollback procedures. [README.md](../README.md) owns normal setup and service operations.

## Implemented

- Private profile, route plans, milestones, inbox, task/document/checklist progress now live in entity tables in `private/workspace.sqlite3`. Legacy JSON is imported once and preserved unchanged; it stops being a live input after PRIVATE initialization. Dashboard, exports, Schola context and offline mirror use committed snapshots.
- Whole-workspace transactions and revision/mode checks prevent partial imports and lost concurrent writes. Conflicts return HTTP 409. Retired identifiers, unknown fields and old checklist records remain recoverable; interactive changes still validate current definitions. Required steps with a historical skip are shown for recheck, and note-only edits preserve their prior progress.
- Workspace and conversation schema versions, foreign keys, state constraints, scope triggers, indexes and pre-migration copies protect data. Missing historical job references receive archived placeholders without changing original message/tool records. Retry receipts prevent delayed/repeated requests from requeueing completed replies.
- App-only SQLite 3.54.1 is pinned to official archive/source hashes and attested under the actual Python interpreters. Runtime wrappers supply it to the web API, worker, watcher and recovery service. Production launchers require it; system libraries remain unchanged.
- Complete local recovery snapshots include both online database copies, eligible vault/configuration/original files, monitor baselines, public definitions and runtime/version files. Hashes, SQLite integrity, references and permissions are verified before publication. Restore requires a new isolated directory. Retention keeps the latest 14 verified copies and preserves invalid/foreign copies.
- The recovery timer is prepared for daily 03:17 WIB plus up to ten minutes of delay, with persistent catch-up. Enable only after a successful drill. Health verifies the newest snapshot and reports stale recovery after 48 hours. Workspace JSON exports remain separate from full recovery snapshots.
- Public catalogue, guides, calendar, owner decisions and Schola research boundaries retain their existing responsibilities. No cloud service, application submission, automatic plan decision or model request was added.

## Checks actually observed

| Check | Result |
| --- | --- |
| `npm run check` | Passed: TypeScript, 86 discovered Python tests (six optional-runtime skips in system Python), 17 Node tests, public data and documentation links. |
| Research/runtime environment | All 86 Python tests passed under the patched runtime with ResourceWarnings treated as errors; package dependency check passed. Both API/system Python and research Python attested SQLite 3.54.1/source identity. |
| Isolated build / privacy / HTTP | Production build passed in a separate checkout. 400 emitted text files and private tracing checks passed. Fictional HTTP checks passed all 57 scholarship pages, persistence, export/import, scoped chat, sessions, exact origins, CSRF and LAN/public isolation. |
| Failure and concurrency checks | Actual TypeScript handlers and Python stores cover large legal exports, impossible dates, future schemas, unknown/retired records, concurrent revision conflicts, coherent export during a partial transaction, interrupted process rollback, retry races, read/write concurrency and demo isolation. |
| Complete recovery | Fixture tests cover WAL inclusion, tamper/corruption, unsafe paths, changing supporting files, retention and isolated restore. A full private copy of the real vault was restored and migrated separately; logical workspace and original conversation records matched exactly. No inference was run. |
| Graph | Code-only local graph rebuilt after implementation with zero model calls. Treat it as navigation and verify source; it omits runtime joins and public data content. |
| Publication | No remote push is part of this release. The next checkpoint must inspect staged paths and blobs, run the privacy hook and compare configured secrets locally without printing them. |

## Live deployment boundary

The existing live web and worker still use the previous release at this preparation checkpoint. Final deployment must wait for zero queued/running jobs and a completed watcher scan, stop old writers, take a final verified pre-migration snapshot, install the tested source/build/runtime, migrate and verify both stores, perform a post-migration restore drill, and start the compatible worker before the web app. Preserve unrelated networking and record actual results here afterward. Never build over the live `.next` output or delete a live lock.

## Known limits

- The user selected local recovery first. Snapshots are plaintext and protected by private permissions. Off-device storage and encryption are deferred; copies on this host do not protect against losing the host.
- A recovery copy is data plus version/runtime metadata and the installed private runtime. A compatible source checkout, dependencies and production build still need installation. Rollback requires a compatible source/build/data set, including any old legacy JSON inputs; switching only code can revive stale data.
- Original private JSON should not be edited as current state after migration. Keep migration copies and complete snapshots; never force a new schema onto an old worker.
- Physical phone/LAN-client behavior and browser visual revalidation were not repeated for this infrastructure release. Existing LAN HTTP remains unencrypted by owner choice; exact protected HTTPS access remains available.
- Guides still cover five public routes; research/eligibility uncertainty and the earlier product limits remain. Source evidence and model answers do not establish personal eligibility or award odds.
