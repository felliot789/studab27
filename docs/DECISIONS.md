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

**Established before the tracker redesign; reaffirmed: 2026-11-04.** Public catalogue, guides, source assessments, code, and fictional examples are versioned. The ignored vault holds real profiles, strategy, progress, documents, conversation, and configuration. Private files load on the server at request time.

This keeps a fresh checkout useful in demo mode and prevents a build or a handoff document from becoming a copy of the owner's workspace. Demo mutations use separate state. File writes are atomic and serialized within one web process; multiple web workers would require a transactional store. See [storage.ts](../src/lib/storage.ts), [access.ts](../src/lib/access.ts), and [AGENTS.md](../AGENTS.md).

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
