# StudAb27

A local scholarship tracker for undergraduate engineering applications. **Tracker**, **Documents**, and **Calendar** keep progress on a chosen set of scholarships together. There is no tracking cap. Schola is available from every page; the catalogue, source updates, scenarios, and settings are secondary tools.

Public code and scholarship references live in Git. Student profiles, financial estimates, application notes, progress, inbox captures, and document imports live in an ignored local vault. A fresh checkout opens with a fictional demo profile.

## Run locally

Requires Node.js 22.18+ (tested with Node 24), npm, Python 3.11+, and Git. On Linux, Poppler's `pdftotext` enables PDF monitoring. The worker has no Python package dependencies. Calendar unit checks use Node's built-in TypeScript support and test runner.

```sh
npm ci
python3 scripts/install-hooks.py
npm run dev
```

Open [the local workspace](http://127.0.0.1:3270). The server binds to loopback. The fictional dashboard works without an account or API key. Schola chat requires your own model connection. No external fonts or analytics are loaded; Next.js telemetry is disabled.

For a production build:

```sh
npm run build
python3 scripts/check-public-build.py
npm start
```

Always use the npm launch scripts or the installed service: they supply the runtime-only configuration path. Directly launching Next without it fails closed. A configured workspace requires a password, including on localhost. A fresh demo without local configuration accepts loopback hosts only. Private data access also checks the session independently of Next's Proxy.

## Finding your work

| Place | What lives here |
| --- | --- |
| Tracker `/` or `/scholarships` | Explicitly tracked scholarships, pursuit priorities, application progress, and the next checklist step |
| Explore `/scholarships?browse=1` | All 57 public routes, outlook filters, and an action to add any route to the tracker |
| Scholarship `/scholarships/[id]` | One permanent page with Checklist, Overview, Dates, Your plan, and Sources |
| Documents `/documents` | Per-scholarship document steps and a separate reusable-pack view; actual files remain in your own folders |
| Calendar `/calendar` | Tracked, saved, and active routes by default, plus an All routes switch and month/agenda views |
| Schola `/schola` | Your durable conversation and read-only research tools |
| Source updates `/updates` | Monitoring, research captures, and budget/SAT scenarios |
| Settings `/settings` | Profile summary, private exports, and explicit backup restoration |
| Earlier tasks `/today` | The existing three-task briefing and focus timer, available through Settings |

Pursuit priority (**Focus**, **Secondary**, **Backup**, or **Decide later**) is separate from application progress. The main target is an explicitly chosen Focus scholarship. Removing tracking preserves its checklist and notes. Existing `/applications`, `/catalogue`, `/bricks`, and `/watchtower` links remain available; older bookmarks and active applications still contribute calendar dates.

The source-scoped guides in `data/public/application_guides.json` distinguish current-cycle evidence, general guidance, and requirements to recheck. Progress and private notes are keyed by both route and step in the vault, shared by the checklist and Documents views. Completing a reusable document never automatically completes a scholarship-specific step. Routes without a researched guide remain trackable without an invented generic checklist. Backups include tracking, priorities, and checklist progress; older backups remain valid. Public presets contain no owner selections.

The scholarship organizer filters **Realistic**, **Reach**, **Lottery**, and **Unknown**, and can hide lottery options while retaining unknowns. Each row and scholarship page explains its assessment with source links and the evidence's cycle. Categories consider admission as well as award selection; a promise of funding after admission does not make the complete path easy. The public source reviews live in `data/public/scholarship_outlooks.json`, separately from personal priorities and the generated catalogue. Missing evidence stays Unknown. No private decisions are changed by filtering.

Published award percentages require recipient and applicant counts for the same award, population and cycle, plus a matching source. The initial reviews do not establish such a rate, and none supports a Realistic classification yet. Counts of awards, admission rates, finalist ratios and percentages of expenses covered are not presented as scholarship success rates. These are dated qualitative research assessments, not calibrated personal predictions or eligibility verification.

## Reviewed catalogue and calendar

The public catalogue includes all 57 refreshed route IDs and 174 calendar records from the 3 November 2026 review. Eighty records have target-cycle date evidence. The remaining 94 include annual rules awaiting cycle confirmation, unresolved dates, and conflicting official sources. They stay in **Dates to confirm**, off calendar days. Funding, language, curriculum, graduation, and other claims retain their own field-level evidence status; a reviewed date does not verify eligibility.

Published times with known zones convert to WIB. Date-only records stay on the publisher's calendar day and never acquire an invented end-of-day cutoff. Multi-day events retain their range. Imported private milestones are labeled personal targets, with published scholarship records shown separately. This calendar does not connect cloud services, submit applications, or send notifications.

`scripts/prepare-catalogue.py REVIEW_DIRECTORY` creates the public projection from reviewed research. It allowlists public facts and source URLs, excluding raw imports, local source filenames, snapshots, hashes, and private review metadata. `scripts/validate-data.py` checks all route/event relationships and date-evidence boundaries. Schola can inspect the same reviewed events without converting candidate dates into verified rules.

## Schola model and conversation

Put the model connection in an ignored `.env` once:

```dotenv
INFERENCE_BASE_URL=http://127.0.0.1:20128/v1
INFERENCE_API_KEY=YOUR_LOCAL_ROUTER_KEY
INFERENCE_MODEL=YOUR_MODEL_ID
```

Then initialize the canonical configuration (never overwrites an existing one):

```sh
python3 scripts/configure-schola.py --from-env --allow-context
```

Thereafter edit **`private/schola.local.json` only** for Schola. The original `.env` is preserved but is no longer its settings source. `schola.example.json` documents the shape without credentials. Model/search changes apply to the next job; no SDK or additional Python packages are required.

| Setting | Purpose |
| --- | --- |
| `llm.baseUrl`, `llm.model`, `llm.apiKey` | Trusted custom-v1 Chat Completions connection; remote endpoints require HTTPS |
| `llm.toolMode` | `json` uses plain-text actions through custom-v1 adapters; `native` uses function calling. Set `llm.jsonResponseFormat` false only if the endpoint rejects JSON response format. |
| `llm.dailyCallLimit` | Model requests per UTC day, including failed attempts; default 80 |
| `llm.maxToolRounds`, `llm.maxOutputTokens`, `llm.timeoutSeconds` | Bound each reply; tools also have a 12-call and ten-minute work budget |
| `contextAllowed` | Explicit consent for relevant real profile, strategy and milestones; false uses fictional context |
| `search.provider` | `searxng`, `brave`, or `disabled` |
| `search.baseUrl`, `search.apiKey` | Local SearXNG URL, or a separate Brave Search API credential |
| `background.enabled`, `background.maxJobsPerDay` | Review newly changed source text in the conversation; default at most three jobs daily |
| `access.origins` | Exact allowed HTTP localhost and HTTPS remote origins, including ports |

Open **Schola** in the app. Messages become durable SQLite jobs, so closing a tab does not cancel work. Drafts stay in the current browser tab until Send is tapped. An interrupted worker marks an unfinished reply failed rather than silently repeating a charged request; retries then require a tap. A malformed JSON reply may receive one bounded format-correction request, counted in the daily budget. There are no automatic network retries or model requests while idle. Conversation history persists in `private/schola.sqlite3`; recent turns enter context, and an older-conversation search tool can retrieve relevant statements. Memory is not official evidence. The UI loads the latest 80 messages.

Tools can read the current plan, compare catalogue routes, search public topics, inspect official HTML/PDF sources, and find older conversation statements. They cannot execute shell commands, submit applications, send messages, mark tasks done, or change verified rules. Relevant project context and chat may reach an external model through your configured router. Credentials and private Calendar/Drive links are excluded from model context; source content is treated as untrusted data. Public search queries reject contact details, credentials and explicit family finances. The reader accepts exact catalogue, search-result, returned-PDF or user-supplied official URLs; it does not invent paths or attach profile data as URL parameters.

**Search is a separate capability from inference.** SearXNG depends on its upstream engines; a successful HTTP response with zero results is not proof of a working search engine. Schola exposes degradation and engine errors, filters to official academic/government and known source domains, and cools down failed searches for five minutes. Direct reading of known official pages remains useful. Brave Search is an optional adapter requiring its own key; no search subscription is provisioned automatically. Neither option promises exhaustive or Google-level discovery.

The assistant can review new `CHANGED` events after a completed watchtower scan. Existing history is a starting watermark, not a new alert. Baselines and errors alone do not trigger model reviews. Reviews appear only in Schola; there is no external messaging channel or idle research loop. Model answers remain fallible even when a tool succeeds; consult the displayed sources before acting.

## Homelab hosting and phone access

After configuration, build and check before enabling the user services:

```sh
npm run check
npm run build
python3 scripts/check-public-build.py
python3 scripts/check-app.py
python3 scripts/install-app-services.py --enable
```

`studab27-web.service` serves production Next at `127.0.0.1:3270`; `studab27-schola.service` processes conversations and source reviews. Both restart on failure. The existing twelve-hour watchtower timer remains separate. No cloud host is needed. Services run while the host and user manager are available; the installer does not change lingering.

The generated password is in **`private/web-login.local.txt`**, mode 0600. It is never displayed by the setup script. The settings hold a scrypt hash and session signing secret; cookies are HttpOnly, SameSite Strict and Secure over HTTPS. Fifteen failed logins temporarily throttle password attempts. To rotate the password and invalidate all sessions, run `python3 scripts/reset-web-password.py`, then read the local password file. The shield menu signs out this browser.

For phone access, add the exact HTTPS origins to `access.origins` first. Prefer private Tailscale Serve; optional Funnel is publicly reachable and therefore also requires login. Use separate free ports and preserve existing services:

```sh
tailscale serve status --json
tailscale serve --bg --https=9443 http://127.0.0.1:3270
tailscale funnel --bg --https=10000 http://127.0.0.1:3270
```

The URLs use your node's exact Tailscale DNS name with `:9443` (tailnet only) or `:10000` (public). Check unauthenticated and authenticated access before relying on them. Never use a default-port command or `reset` that might replace unrelated 443/8443 mappings. Disable only these routes with `tailscale serve --https=9443 off` or `tailscale funnel --https=10000 off`. To stop the app, use `systemctl --user disable --now studab27-web.service studab27-schola.service`.

The phone layout uses bottom navigation, cards by default, larger form controls, safe-area spacing, full-height drawers, and a reachable focus bar. Browser viewport checks do not replace testing an actual phone and its on-screen keyboard.

## Private data and demo mode

Without `private/profile.local.json` and `private/overlay.local.json`, the app loads fictional public examples. To force the demo even when a real vault exists:

```sh
STUDAB27_DEMO=1 npm run dev
```

Demo progress, route edits and conversation storage are separate from real-user state. Forced demo mode also disables real model credentials and private chat/context. To initialize a local vault from a private project seed stored outside the checkout:

```sh
python3 scripts/bootstrap-private.py --seed /absolute/path/to/project-seed.md
```

The bootstrap never overwrites existing files. Running it without `--seed` copies fictional examples into the local vault. Do not put the combined original seed document into tracked source.

Open **Your local vault** from the shield button to download a private JSON backup or restore a StudAb27 v1 export. Imports show a review step, validate every route, and keep a recovery bundle under `private/backups/` before replacing files. A failed write attempts rollback from that bundle. File writes use atomic replacement; this single-process local app serializes mutations. Use a database and transactions before adding multiple server workers.

The optional offline Drive mirror exporter writes into the ignored vault:

```sh
python3 -m schola.drive_sync private/exports/my-backup
```

It maps records to `00_HQ`, `01_Catalogue`, `02_Applications`, `03_School_Documents`, `04_Financial_Documents`, `05_Profile_Evidence`, `06_Offers_and_Decisions`, `07_Inbox`, and `99_Archive`. Existing export folders are preserved. JSON exports do not include original imported DOCX/XLSX, supporting documents, conversation SQLite data or model/access settings: back up those separately. **Google Drive and Calendar are not connected or automatically synchronized.** Imported Calendar links are historical references; no Calendar events are created.

## What Schola does

- **Briefing:** the five initial task templates are followed by specific document steps, checks for active routes, and near-term personal milestone checks. At most three are shown. Done, snooze, replacement, and route decisions require explicit user actions. Snooze lasts 24 hours; replacement moves a task behind other work. Completed tasks can return to the queue. The focus timer uses the current clock, survives navigation within the tab, and never completes a task automatically.
- **Catalogue:** search and filter by country, private strategy, SAT role, and budget estimate. Each route has a drawer for source notes, renewal/bond terms, readiness packs, status, private notes, optional itemized cost estimates, and human-checked program rules.
- **Gates:** curriculum and graduation checks remain unknown without an explicitly recorded program-specific, current-cycle source. The budget check compares a conservative range or an itemized monthly cost minus coverage against the profile cap. An overlapping range stays unknown. Missing data is never zero. Upfront arrival cash is separate and can still make a route unsustainable.
- **Simulator:** scenario SAT and budget controls recalculate the same Python evaluator used elsewhere. Advisory SAT targets are not admission thresholds. The simulator never changes the saved profile and never treats unknown rules as an unlocked scholarship.
- **Watchtower:** bounded HTML/PDF fetches, SHA-256 of normalized text, source snapshots, diffs, and visible errors. First fetch establishes a baseline. Failed fetches retain the last good hash. Changed text does not automatically establish a new deadline or eligibility rule. Inbox links are never fetched automatically.

Scholarship benefits, requirements, and deadlines in the original catalogue are **unverified seed claims**. Scoped official-source checks are stored separately in `data/public/source_verifications.json`, including the corrected UBC international-award deadline and the uncertain PoliTO testing transition. A checked deadline does not verify every other claim in that route. No applications are submitted. Award-specific restrictions on AI-created content, including Pearson's, must be respected.

## Monitoring

Run one local scan:

```sh
python3 -m schola.watcher
```

Results go to `private/watchtower_state.local.json`; text snapshots stay under `private/watchtower/snapshots/`. The monitor fetches catalogue sources, scoped source-note URLs, and at most two discovered same-host PDF links per page. It limits response size/read time, uses four workers with per-host serialization, validates and pins public IPs for each HTTP(S) redirect, and prevents overlapping scans with a file lock. It does not crawl entire university websites, run JavaScript, bypass access controls, or interpret every changed sentence.

On a Linux system with a user systemd manager:

```sh
python3 scripts/install-local-timer.py --enable
```

The timer runs around **07:17 and 19:17 WIB**, with up to five minutes of jitter, and catches up missed runs when the user manager returns. It cannot run while the computer is off; user-manager availability also matters. It does not enable lingering or alter unrelated services. Inspect or stop it with:

```sh
systemctl --user status studab27-watchtower.timer
systemctl --user list-timers studab27-watchtower.timer
journalctl --user -u studab27-watchtower.service
systemctl --user disable --now studab27-watchtower.timer
```

If the shell lacks a user-bus environment, use `XDG_RUNTIME_DIR=/run/user/$(id -u)` and `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus` for those commands.

`.github/workflows/schola-watchtower.yml` provides manual and 12-hour GitHub Actions scans after the repository is deliberately published and Actions are enabled. It reads no private profile, preserves public source baselines in the Actions cache, and uploads public observations as an artifact. Cache eviction resets a source to a first baseline. The workflow is not active just because this local file exists. Neither local scans nor CI send email or push notifications; results appear in the app or CI artifact.

## Privacy guard and checks

`scripts/check-privacy.sh` scans **staged Git blobs**, including force-added ignored paths. It blocks vault/local/env paths, known seed identifiers, private Drive/Calendar links, private keys, and binary files requiring review. It never prints matching private content. This is a guardrail rather than a general personal-data detector: review staged diffs before publishing, especially new free text or assets. Git hooks are local and must be installed after cloning.

```sh
npm run check
npm run build
python3 scripts/check-public-build.py
python3 scripts/check-app.py
```

Checks cover conservative gates, task queues, source baselines/errors and public-IP pinning, staged privacy, durable chat/retries, JSON tool compatibility, model budgets, context redaction, demo isolation and degraded search. The production HTTP check uses a disposable fictional workspace for persistence, exact hosts/origins, login, forged cookies, HTTPS cookie flags, protected exports and import recovery. The build check scans emitted code for seed identifiers and configured secrets, and traces for private/env paths. Stubbed provider tests do not prove a particular live model works; test the configured model separately. Fetch success and a timer do not prove every scholarship rule is verified.

## Repository map

| Location | Responsibility |
| --- | --- |
| `src/app/` | Five dynamic app pages, login and protected JSON APIs |
| `src/components/` | Accessible dashboard, route drawer, checklists, simulator |
| `src/lib/storage.ts` | Runtime-only vault/demo loading and serialized file writes |
| `schola/evaluator.py` | Conservative deterministic gates and advisory scenarios |
| `schola/spoonfeeder.py` | Atomic task pool and bounded briefing queue |
| `schola/watcher.py` | Public-source fetches, text normalization, snapshots, diffs |
| `schola/assistant.py` | SQLite conversation/jobs, bounded model/tool loop, source reviews |
| `schola/config.py` | Local model/search settings and browser-safe status |
| `schola/drive_sync.py` | Offline export into canonical Drive-shaped folders |
| `data/public/` | Catalogue, fictional presets, task definitions, scoped sources |
| `private/` | Ignored personal state, source imports, snapshots, recovery bundles |

The product direction is in `PRODUCT.md`; project safety and development conventions are in `AGENTS.md`.
