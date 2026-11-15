# Decisions

Read [PRODUCT.md](../PRODUCT.md) for the current product direction and [REPO_MAP.md](REPO_MAP.md) for implementation locations. These records explain choices; they do not record the owner's scholarship selections. Update an entry when its decision changes, with the reason and date.

## 1. A tracker is the primary workspace

**Adopted: 2026-11-04.** Tracker, Documents, and Calendar are primary. The full catalogue, source monitoring, scenarios, and older briefing remain accessible as secondary tools. Tracking has no numerical cap; a small working set is a user choice.

The earlier broad dashboard made it hard to understand where to start. Each scholarship now has a permanent page opening on its checklist. New work should help the user make progress on chosen applications, without turning home back into a control room. See [tracker.tsx](../src/components/tracker.tsx) and [workspace.tsx](../src/components/workspace.tsx).

## 2. Priority, progress, outlook, and eligibility are independent

**Adopted: 2026-11-04.** Pursuit priority is Focus, Secondary, Backup, or unset (Decide later). Application progress records preparation. Outlook describes selection difficulty. Eligibility gates describe available evidence. None implies another.

The main target is explicitly chosen and always Focus; removing tracking retains notes and progress. Unknown priorities remain unset. A Reach assessment must never demote a user-chosen priority automatically. See [schema.ts](../src/lib/schema.ts), [tracker.ts](../src/lib/tracker.ts), and [the mutation API](../src/app/api/schola/route.ts).

## 3. Requirements belong to a scholarship and source scope

**Adopted: 2026-11-04.** Public guides define route-specific steps with source references and cycle/recheck information. Private completion and notes are keyed by route ID and step ID. Documents and the scholarship checklist edit the same progress.

A reusable passport or transcript being ready does not prove it meets a university's format, translation, recency, or submission rules. Shared readiness is a hint only. A route without a researched guide remains trackable and says the guide is missing. See [application_guides.json](../data/public/application_guides.json), [application-checklist.tsx](../src/components/application-checklist.tsx), and [bricks.tsx](../src/components/bricks.tsx).

## 4. Scholarship odds require matching evidence

**Adopted: 2026-11-04.** Realistic, Reach, Lottery, and Unknown describe the whole path to receiving the award, including admission when required. Percentages require matching scholarship-recipient and applicant counts for the same population and cycle.

Automatic funding after admission is not evidence of an easy overall path. Admissions rates, finalist ratios, funding coverage, and scenario SAT scores are not personal award probabilities. Leave unsupported cases Unknown, even if Realistic is empty. See [scholarship_outlooks.json](../data/public/scholarship_outlooks.json) and [scholarship-outlook.ts](../src/lib/scholarship-outlook.ts).

## 5. Public definitions and private runtime state stay separate

**Established before the tracker redesign; revised: 2026-11-07.** Public catalogue, guides, source assessments, code and fictional examples are versioned. The ignored vault holds canonical workspace/conversation SQLite stores, original documents, configuration and monitor files. Private records load on the server at request time. Legacy workspace JSON is imported once and retained as historical input.

This keeps a fresh checkout useful in demo mode and prevents a build or handoff from copying the owner's workspace. Forced demo uses separate databases. Workspace transactions and revision checks coordinate independent writers; monitor/export and migration-bundle writes use restrictive atomic replacement and fsync. See [storage.ts](../src/lib/storage.ts), [access.ts](../src/lib/access.ts), and [AGENTS.md](../AGENTS.md).

## 6. Missing evidence and failed work preserve uncertainty

**Established before the tracker redesign; reaffirmed: 2026-11-04.** Missing eligibility facts remain UNKNOWN. Calendar days contain source-supported dates; pending and conflicting dates remain separate. Date-only records do not acquire invented cutoffs. A first successful source fetch is a baseline, not a change; failed fetches preserve it.

Schola uses durable SQLite jobs, bounded model/tool budgets, and explicit retry after interrupted work. Its tools research and read; they cannot submit applications or change user decisions. Source text and model output remain untrusted evidence. See [calendar.ts](../src/lib/calendar.ts), [evaluator.py](../schola/evaluator.py), [watcher.py](../schola/watcher.py), and [assistant.py](../schola/assistant.py).

## 7. Native controls retain semantics while the UI stays quiet

**Adopted: 2026-11-04.** Selectors use styled native controls, including `appearance: base-select` where supported, with a native fallback. Country flags are small supporting labels; text remains the source of meaning.

Preserve keyboard access, visible focus, contrast, and reduced motion. Browser support limits visual uniformity; avoid adding a component library just to remove the fallback. See [redesign.css](../src/app/redesign.css) and [ui.tsx](../src/components/ui.tsx).

## 8. The handoff works without a graph service

**Adopted: 2026-11-04.** Versioned Markdown holds product intent, architecture, decisions, and dated status. Optional Graphify output is ignored and regenerated locally with `npm run map` using structural code extraction and clustering without model labels.

The graph helps locate relationships; it does not replace source review or capture product intent automatically. No model credentials, cloud account, background watcher, or harness-specific server is required. Update the written map as code changes, and rebuild the graph before relying on it. See [README.md](../README.md#optional-code-graph) and [.graphifyignore](../.graphifyignore).

## 9. Optional separate LAN login

**Adopted: 2026-11-04 at the owner's request.** An exact LAN HTTP origin may use a separate password and session secret, only through a reverse proxy that inserts an unguessable private header. The application remains loopback-only and the public HTTPS login remains separate. LAN HTTP is unencrypted. The proxy must overwrite the header from clients; keep its configuration in the private vault.

## 10. Scholarship Schola specializes through isolated conversations

**Adopted: 2026-11-05 at the owner's request.** Every scholarship detail page offers a popup using the existing Schola model and worker with route-scoped context, tools, history and browser-tab drafts. General Schola remains the home for broader research, comparisons and background source reviews. A separate model or provider connection is unnecessary; settings and daily call budgets remain shared.

Validate the route ID on the server and preserve it through durable jobs, replies and explicit retries. Never infer scope from a prompt or let a specialist retrieve other scholarships' private conversation or plans. Existing history remains general; closing a popup cannot discard a draft or queued job. Deploy the scope-aware worker and web together. The Description tab reuses catalogue facts and source assessments; no new eligibility or funding claim is inferred. See [assistant.py](../schola/assistant.py), [schola-chat.tsx](../src/components/schola-chat.tsx), and [scholarship-detail.tsx](../src/components/scholarship-detail.tsx).

## 11. Schola researches adaptively; the owner manages the journey

**Adopted: 2026-11-05 at the owner's request.** Fluent research is the primary feature: public discovery, reading official pages, following relevant links/PDFs, reformulating searches and explaining evidence gaps. Scholarship conversations retain findings and provenance; general Schola handles broader questions. The scheduled watcher remains separate. Neither agent mode chooses routes, completes tasks or submits applications.

Use the MIT-licensed LangGraph orchestration runtime with Schola's existing model transport and restricted tools. Local Deep Research was investigated as a fuller research engine, but its supported package adds embedding, document and web-server dependencies unrelated to this app; a partial no-dependencies installation would be unsupported. The implemented graph uses the same orchestration project directly, without importing that product's wider tool surface. No provider SDK, search subscription or managed agent service is required; inference and hosting are separate costs. See [requirements-research.txt](../requirements-research.txt) and [research_harness.py](../schola/research_harness.py).

SQLite remains responsible for durable jobs, scoped memory, call accounting and explicit retry. Model/tools execute serially on its owning worker thread; ambient remote tracing is disabled. The graph and built-in compatibility loop share the same bounded callbacks. Source reading validates public IPs across redirects and admits exact discovered official links. Fetched evidence remains untrusted and cannot change verified rules. Free search engines can fail; report degradation and continue through known official sources rather than interpreting zero results as absence.

## 12. Transactional workspace and local recovery

**Adopted: 2026-11-07.** Keep SQLite for the local workload. `workspace.sqlite3` owns profile/plans/milestones/inbox/progress; `schola.sqlite3` owns durable conversations/jobs/provenance/budgets. Entity keys, constraints and foreign keys preserve structure, while JSON bodies retain unknown fields and retired catalogue identifiers. Whole-workspace transactions plus revision/mode checks prevent partial imports and stale concurrent overwrites. Existing legacy JSON stays unchanged and stops being a live input after migration. Both stores have explicit schema versions; chat retry receipts prevent repeated delivery from repeating completed work.

Use an app-only checksum-pinned SQLite library under the vault through launcher wrappers. Production units require it; the system library and unrelated applications remain untouched. Schema changes deploy with compatible web/worker code after jobs finish and old writers stop. Rollback restores a compatible source/build/data set; switching only code would expose stale legacy records or incompatible databases.

Complete local snapshots include eligible vault/configuration/original files, both online SQLite backups, source baselines, public definitions and runtime/version records. Capture refuses active scans, unsafe paths/links, unknown databases or changing supporting files. Restore creates a new isolated directory. Daily 03:17 WIB scheduling is opt-in, retains the latest 14 verified snapshots and reports stale recovery after 48 hours. Damaged and unrecognized copies are preserved.

**Clarified: 2026-11-15.** Vault-root operational copies, including legacy `releases` and `lan-previous-build`, are excluded from data snapshots. Identically named folders within original supporting documents remain eligible. Rollback source/build/data bundles are retained separately; generated build caches must not multiply with daily recovery copies.

The user selected local recovery before choosing external storage. Copies are plaintext, protected by 0700/0600 permissions; encryption and off-device recovery are explicitly deferred. No cloud connection or host-loss protection is implied. See [DATABASE.md](DATABASE.md) for exact coverage, exclusions and operational procedures; [recovery.py](../schola/recovery.py) and [workspace_store.py](../schola/workspace_store.py) implement these boundaries.

## 13. Research extends the catalogue without moving owner state

**Adopted: 2026-11-15.** Engineering and computer science are in scope. Official-source research may add public routes and source-scoped guides while preserving existing route IDs and checklist identities. Combined university funding pages retain their scope; mechanisms are described separately without silently migrating plans. An external sponsor is a separate route until an exact host pairing is established. Catalogue counts are derived from data, while unique IDs, reference integrity and evidence/date invariants remain required. See the [research checkpoint](RESEARCH-2026-11-15.md).


## 13. Schola proposes; explicit acceptance adds to the local catalogue

**Adopted: 2026-11-16 at the owner's request.** Store scholarship drafts and accepted local routes in the existing transactional workspace state, under `scholarshipDrafts` and `localScholarships`. The versioned public catalogue remains the reusable base. Stable `local-<draft UUID>` identifiers keep additions separate, while workspace export/import and full recovery preserve them without a new database or SQL migration.

Only an explicitly requested `scholarship-draft` job receives `propose_scholarship`. It can save a draft using source URLs actually read in that job, with server-recorded retrieval times. It cannot accept, track, prioritize or verify a route. These public research jobs omit owner profile and conversation memory. The review UI saves edits with revision checks and adds a local entry only through explicit acceptance. Exact institution/award duplicates return the existing entry; distinct awards at one institution remain separate. The final tool slot and model reply are reserved for draft persistence when retrieval reaches its limits.

Exact public links supplied by the user, returned by search or present in fetched pages may be read through the pinned public-address fetcher. Admission permits reading, not a claim of institutional authority or verified eligibility; private links, credential URLs and invented paths stay blocked. Closed/later-cycle evidence remains labeled, unsupported fields stay UNKNOWN, and local additions receive neither calendar events nor researched checklists automatically. Publishing additions to Git is a separate review. See [catalogue.py](../schola/catalogue.py), [catalogue API](../src/app/api/schola/scholarships/route.ts), [draft review](../src/components/scholarship-drafts.tsx) and [source policy](../schola/source_policy.py).
