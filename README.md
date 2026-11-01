# StudAb27

A local scholarship workspace for undergraduate engineering applications. Schola keeps official-source snapshots, calculates conservative planning gates, and offers at most three short next steps. The interface includes a briefing, a 57-route catalogue, four reusable document packs, and a source watchtower with a SAT and budget simulator.

Public code and scholarship references live in Git. Student profiles, financial estimates, application notes, progress, inbox captures, and document imports live in an ignored local vault. A fresh checkout opens with a fictional demo profile.

## Run locally

Requires Node.js 20.9+ (tested with Node 24), npm, Python 3.11+, and Git. On Linux, Poppler's `pdftotext` enables PDF monitoring. The worker has no Python package dependencies.

```sh
npm ci
python3 scripts/install-hooks.py
npm run dev
```

Open [the local workspace](http://127.0.0.1:3270). The server binds to loopback. No accounts, external fonts, cloud credentials, analytics, or paid API keys are needed. Next.js telemetry is disabled by the project scripts.

For a production build:

```sh
npm run build
python3 scripts/check-public-build.py
npm start
```

The app intentionally has no remote-user authentication. Keep it local. Hosting the personal vault or exposing this server requires a separately reviewed authentication and deployment design; the repository can be public without making the running personal app public.

## Private data and demo mode

Without `private/profile.local.json` and `private/overlay.local.json`, the app loads fictional public examples. To force the demo even when a real vault exists:

```sh
STUDAB27_DEMO=1 npm run dev
```

Demo progress and route edits are stored separately from real-user state. To initialize a local vault from a private project seed stored outside the checkout:

```sh
python3 scripts/bootstrap-private.py --seed /absolute/path/to/project-seed.md
```

The bootstrap never overwrites existing files. Running it without `--seed` copies fictional examples into the local vault. Do not put the combined original seed document into tracked source.

Open **Your local vault** from the shield button to download a private JSON backup or restore a StudAb27 v1 export. Imports show a review step, validate every route, and keep a recovery bundle under `private/backups/` before replacing files. A failed write attempts rollback from that bundle. File writes use atomic replacement; this single-process local app serializes mutations. Use a database and transactions before adding multiple server workers.

The optional offline Drive mirror exporter writes into the ignored vault:

```sh
python3 -m schola.drive_sync private/exports/my-backup
```

It maps records to `00_HQ`, `01_Catalogue`, `02_Applications`, `03_School_Documents`, `04_Financial_Documents`, `05_Profile_Evidence`, `06_Offers_and_Decisions`, `07_Inbox`, and `99_Archive`. Existing export folders are preserved. JSON exports do not include the original imported DOCX/XLSX or the actual supporting documents: back up those separately. **Google Drive and Calendar are not connected or automatically synchronized.** Imported Calendar links are historical references; no Calendar events are created.

## What Schola does

- **Briefing:** the five initial task templates are followed by specific document steps, checks for active routes, and near-term personal milestone checks. At most three are shown. Done, snooze, replacement, and route decisions require explicit user actions. Snooze lasts 24 hours; replacement moves a task behind other work. Completed tasks can return to the queue. The focus timer uses the current clock, survives navigation within the tab, and never completes a task automatically.
- **Catalogue:** search and filter by country, private strategy, SAT role, and budget estimate. Each route has a drawer for source notes, renewal/bond terms, readiness packs, status, private notes, optional itemized cost estimates, and human-checked program rules.
- **Gates:** curriculum and graduation checks remain unknown without an explicitly recorded program-specific, current-cycle source. The budget check compares a conservative range or an itemized monthly cost minus coverage against the profile cap. An overlapping range stays unknown. Missing data is never zero. Upfront arrival cash is separate and can still make a route unsustainable.
- **Simulator:** scenario SAT and budget controls recalculate the same Python evaluator used elsewhere. Advisory SAT targets are not admission thresholds. The simulator never changes the saved profile and never treats unknown rules as an unlocked scholarship.
- **Watchtower:** bounded HTML/PDF fetches, SHA-256 of normalized text, source snapshots, diffs, and visible errors. First fetch establishes a baseline. Failed fetches retain the last good hash. Changed text does not automatically establish a new deadline or eligibility rule. Inbox links are never fetched automatically.

Scholarship benefits, requirements, and deadlines in the original catalogue are **unverified seed claims**. Scoped official-source checks are stored separately in `data/public/source_verifications.json`, including the corrected UBC international-award deadline and the uncertain PoliTO testing transition. A checked deadline does not verify every other claim in that route. No application prose is generated or submitted.

## Monitoring

Run one local scan:

```sh
python3 -m schola.watcher
```

Results go to `private/watchtower_state.local.json`; text snapshots stay under `private/watchtower/snapshots/`. The monitor fetches catalogue sources, scoped source-note URLs, and at most two discovered same-host PDF links per page. It limits response size, uses four workers with per-host serialization, validates public HTTP(S) redirect targets, and prevents overlapping scans with a file lock. It does not crawl entire university websites, run JavaScript, bypass access controls, or interpret every changed sentence.

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

The tests cover funding boundaries, unknown evidence, graduation cutoffs, queue behavior, source normalization and baseline/error handling, staged-blob privacy, and production HTTP flows. The HTTP check creates a disposable fictional workspace to exercise persistence, origin/host guards, simulation, export, import, and recovery backups without altering the real vault. The build check scans emitted production code and traces for known seed identifiers and private paths. Live fetch success and the existence of a timer do not prove every source is reliable or every scholarship rule is verified.

## Repository map

| Location | Responsibility |
| --- | --- |
| `src/app/` | Four dynamic app pages and local JSON API |
| `src/components/` | Accessible dashboard, route drawer, checklists, simulator |
| `src/lib/storage.ts` | Runtime-only vault/demo loading and serialized file writes |
| `schola/evaluator.py` | Conservative deterministic gates and advisory scenarios |
| `schola/spoonfeeder.py` | Atomic task pool and bounded briefing queue |
| `schola/watcher.py` | Public-source fetches, text normalization, snapshots, diffs |
| `schola/drive_sync.py` | Offline export into canonical Drive-shaped folders |
| `data/public/` | Catalogue, fictional presets, task definitions, scoped sources |
| `private/` | Ignored personal state, source imports, snapshots, recovery bundles |

The product direction is in `PRODUCT.md`; project safety and development conventions are in `AGENTS.md`.
