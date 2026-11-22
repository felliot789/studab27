# Database and local recovery

This describes the implementation and maintenance procedure, not a live deployment result. See [HANDOFF.md](HANDOFF.md) for the observed release baseline and checks, [REPO_MAP.md](REPO_MAP.md) for callers, and [DECISIONS.md](DECISIONS.md#12-transactional-workspace-and-local-recovery) for the design choice.

## Authoritative stores

| Store | Responsibility |
| --- | --- |
| `private/workspace.sqlite3` | Profile, route plans, milestones, inbox, task progress, reusable-document readiness and scholarship checklist progress, scholarship drafts and accepted local catalogue entries. |
| `private/schola.sqlite3` | Conversation jobs, messages, research provenance, budgets, worker state and explicit retry receipts. |
| `private/demo-workspace.sqlite3`, `private/demo-schola.sqlite3` | Isolated stores when `STUDAB27_DEMO=1`; owner credentials/context and import are disabled. |
| `data/public/` | Versioned catalogue, guides, calendar, source reviews and fictional examples. |
| Remaining vault files | Model/access configuration, original supporting files, monitor state/text snapshots, local runtime and recovery copies. |

Workspace schema v1 imports legacy profile/overlay/state/milestone/inbox JSON once, in a transaction, and leaves the original files unchanged. **After migration, those JSON files are historical inputs, not live records.** Edit through the app or its validated import; changing an old JSON file does not change a private workspace or Schola's context. The offline Drive mirror also reads the canonical workspace once initialized.

Before initialization, both owner profile and overlay must exist to select PRIVATE mode; a partial pair fails closed. Without them, ordinary first use initializes a DEMO workspace. Explicitly bootstrapping an owner pair can activate that workspace as PRIVATE, with a prior-state recovery bundle. Forced demo uses the separate stores above regardless of owner files.

### Workspace entities

| Table | Key and invariant |
| --- | --- |
| `workspace_meta` | One row: PRIVATE/DEMO mode, positive revision and additional state fields. |
| `profile` | One JSON-object record, retaining unrecognized fields. |
| `route_plans` | Stable route ID, unique list position and JSON body. At most one main target; it must be tracked and Focus. |
| `milestones`, `inbox` | Ordered records; inbox IDs are unique and status is NEW or TRIAGED. |
| `task_progress`, `brick_progress` | Stable task/item keys; completion state and additional task fields. |
| `requirement_progress` | Route/item pair; foreign key to a retained plan and an allowed checklist status. |
| `migrations` | Applied workspace schema version, time and description. |

Definitions may retire a route, task or guide item without deleting private history. Migration, export/import and database reads retain those identifiers and unknown fields. New interactive edits still validate against current public definitions. A stored retired route does not become a currently available scholarship.

Drafts and accepted additions are validated optional objects in `workspace_meta.state_extra`, under `scholarshipDrafts` and `localScholarships`. They retain stable UUID-based identities, source findings, unresolved questions and per-draft revisions. The SQL schema remains v1. A portable workspace export includes both objects; the separately versioned public catalogue and chat remain outside that bundle. Local records cannot shadow public route IDs or import field reviews as verified eligibility.

### Conversation entities

| Table | Responsibility |
| --- | --- |
| `jobs` | Durable QUEUED → RUNNING → DONE/FAILED state. |
| `job_scopes` | Scholarship scope for a specialist or scoped investigation job. Absence means no scholarship scope. |
| `messages`, `tools` | Conversation content and research provenance referencing jobs. Scope triggers prevent moving saved content between conversations. |
| `calls`, `kv` | Nonnegative daily model-call counts and JSON worker/settings state. |
| `retry_requests` | Explicit retry identifiers, making repeated delivery of the same retry safe. |
| `legacy_job_references` | Archived placeholders preserving historic references to missing jobs; omitted from queues and retry. They do not claim a completed model answer. |

Chat schema v2 adds `research_sessions` (brief, origin, topic and unread state), `research_jobs` (session membership and stopped or redirected outcomes), and `research_findings` (source excerpts linked to completed tools). The v1 → v2 migration is additive and makes a consistent pre-migration chat backup. General and scholarship chat exclude research-session turns. Session and evidence records are included in full local recovery.

The workspace remains at schema v1. Both databases use foreign keys, bounded busy waits and FULL synchronization. Writable use restores WAL mode after schema compatibility checks, including when opening a standalone recovery copy. Newer schemas are refused. Chat migration preserves legacy content and creates a consistent pre-migration database copy before rebuilding constrained tables.

## Reads, writes and limits

[storage.ts](../src/lib/storage.ts) loads one committed workspace snapshot through [workspace_store.py](../schola/workspace_store.py). A mutation sends that snapshot's revision and mode back to Python. `BEGIN IMMEDIATE` checks both before replacing entity rows and advancing the revision in one commit. A competing writer causes HTTP 409; refresh and retry. An interrupted save or import rolls back the entire transaction. The web process queue reduces local conflicts; SQLite and revision checks provide correctness across independent processes.

Dashboard, export, Schola context and the offline mirror read the canonical store. Public definitions and monitor files remain separate reads. The workspace supports 16 MiB of encoded data, up to 500 inbox records, and bounded fields. The 32 MiB import/bridge limit leaves room for request/JSON overhead; the browser uses the same import limit. A v1 JSON export is a portable workspace bundle, not a complete recovery snapshot: it excludes chat, credentials, original files and monitor baselines. Import preserves a pre-import workspace bundle under `private/backups/` inside the write transaction before updating rows; a failed bundle write prevents the update.

## Pinned application runtime

[install-sqlite-runtime.py](../scripts/install-sqlite-runtime.py) builds checksum-pinned SQLite 3.54.1 from the official amalgamation into `private/runtime/sqlite-3.54.1/`. It requires Linux, an existing C compiler and Python; it installs no global library or Python package. The receipt pins the source and compiled library. Checks attest the actual library loaded by system Python and an existing research interpreter.

```sh
python3 scripts/install-sqlite-runtime.py
python3 scripts/install-sqlite-runtime.py --check
```

If the research environment is created later, repeat `--check` to attest it too. [run-python.py](../scripts/run-python.py) supplies the verified library before starting Python; [run-web.py](../scripts/run-web.py) passes it to Next and its Python children. Production web, worker, watcher and recovery units require the runtime and fail closed if it is missing or invalid. Use these launchers rather than direct production Python/Next commands. The wrapper's checkout determines the runtime; `--root` selects the data being maintained.

## Complete local snapshots

```sh
python3 scripts/run-python.py -m schola.recovery create
python3 scripts/run-python.py -m schola.recovery verify /absolute/path/to/snapshot
python3 scripts/run-python.py -m schola.maintenance health
```

The default destination is `private/recovery/`; a custom destination must remain inside the ignored vault. Snapshot publication uses restrictive temporary directories, file/directory fsync and atomic rename. The manifest records every captured file's SHA-256 and size, both databases' schema metadata, missing databases, coverage/exclusions and source/Python/SQLite versions. Verification checks all recorded bytes, unexpected files, database integrity, foreign keys and private permissions.

Coverage includes both owner databases through SQLite's online backup API, eligible original vault files/configuration, source-monitor state and text baselines, public definitions, and package/requirements version files. An installed app-only SQLite library and receipt inside the vault are included. Source code, installed dependencies and production builds require a compatible checkout/reinstallation; this is an isolated data restore, not a runnable source archive.

The watcher lock is acquired without waiting; an active scan is left alone and capture fails for a later retry. Each database has an independently pinned read transaction, including committed WAL content. Supporting-file inventories/fingerprints and hashes must remain stable across capture. These are independent stores, not one distributed transaction. Copied databases use standalone DELETE journaling for transport; compatible writable app access restores WAL.

The exclusion policy is deliberately scoped:

- At the vault root: `recovery`, `backups`, `deployments`, `releases`, `lan-previous-build`, `node_modules`, `.next`, `__pycache__`, `artifacts`, `.venv` and `.venv-research` directories; the selected recovery destination is also excluded. The two legacy release directories contain rollback artifacts and must not be copied into every data snapshot.
- Known root demo workspace/chat/profile/overlay/state/milestone/inbox stores and their database sidecars.
- Root lock, temporary, log, PID, socket and editor-backup files; watcher snapshot `.tmp` files; runtime installation lock and `.sqlite-*` staging directories.
- Canonical database WAL/SHM/journal sidecars, whose committed content is captured through the database API instead of raw copying.

Nested original-document folders named `cache`, `backups`, `deployments`, `releases`, `lan-previous-build` or `artifacts`, and attached `.log`/`.tmp` files, are preserved. Eligible symlinks/special files, unexpected databases, unsafe paths or a changed supporting-file set cause failure rather than silent omission. Snapshot verification/restore reject links, traversal, missing/extra files and altered hashes. Missing databases are explicitly listed, permitting a pre-migration snapshot without inventing an initialized store.

Snapshots are **plaintext private data, including credentials**: directories are 0700, files 0600. Hashes detect damaged copies; they are not encryption or an external signature. The user chose local recovery first. **Off-device storage and encryption are deferred**, and health/manifest output explicitly says off-device recovery is unverified. Same-host copies cannot protect against losing the host.

### Scheduling and health

```sh
python3 scripts/install-recovery-service.py
# Explicitly enable after a successful snapshot and restore drill:
python3 scripts/install-recovery-service.py --enable
systemctl --user status studab27-recovery.timer
journalctl --user -u studab27-recovery.service
python3 scripts/run-python.py -m schola.maintenance health
```

The installer prepares units without starting/enabling them by default. The timer runs at **03:17 WIB (Asia/Jakarta)** with up to ten minutes of delay and persistent catch-up when the user manager returns. It cannot run on a powered-off computer and does not enable lingering. It retains the latest **14 verified tool-owned snapshots**, not fourteen calendar days. Invalid, foreign and unfinished copies are preserved for investigation; retention never deletes outside its own snapshot namespace.

Recovery health fully verifies the newest snapshot: OK through 48 hours, STALE after that, MISSING when none exists, INVALID when the newest copy fails verification. An invalid newest copy is reported even if an older good one exists. Inspect the database and recovery fields, not just the maintenance command's exit code. Timer activity alone does not establish recovery health. Full verification reads the complete snapshot; use it for maintenance rather than frequent UI polling.

## Migration and deployment runbook

1. Build and validate a separate checkout while production serves its existing `.next`. Install/attest the pinned runtime and any selected research environment. Preserve the tested source/build pair and the previous release for rollback.
2. Stop accepting new owner edits/sends, wait until queued/running jobs are zero, then stop the old web/worker writers. Preserve timer states and let any watcher scan finish before pausing its timer. Do not terminate paid work or delete live locks. Keep `STUDAB27_DEMO` unset for owner maintenance.
3. Create and verify a final **pre-migration** complete snapshot after writers are quiescent. The checked checkout can operate on the live vault before its code is switched:

   ```sh
   python3 /absolute/checked/scripts/run-python.py -m schola.recovery --root /absolute/live create
   python3 /absolute/checked/scripts/run-python.py -m schola.recovery verify /absolute/pre-migration-snapshot
   ```

4. Deploy the tested source/build together, install/attest its runtime at the live location, and review/update differing service units to use the wrappers. Existing unit installers preserve differing units; do not enable incompatible old commands. From that checkout:

   ```sh
   python3 scripts/run-python.py -m schola.maintenance migrate
   python3 scripts/run-python.py -m schola.maintenance health
   python3 scripts/run-python.py -m schola.recovery create
   ```

   Migration refuses queued/running chat jobs. Keep its legacy seed/chat copies under `private/backups/`; these are additional migration safeguards, not full recovery snapshots.
5. Verify the post-migration snapshot and perform the isolated restore drill below. Start the compatible worker before the web app, restore the intended watcher schedule, and enable the daily recovery timer after the drill. Confirm schema/integrity/backup status, application data and both authenticated access and unauthenticated denial. A successful service start alone is insufficient.

## Restore drill and rollback

Restore always requires a **new directory outside the live checkout and recovery storage**. It never overwrites the current vault. Put global `--root` before the command when selecting a data root:

```sh
python3 scripts/run-python.py -m schola.recovery --root /absolute/live restore /absolute/snapshot /absolute/new-isolated-drill
python3 scripts/run-python.py -m schola.maintenance --root /absolute/new-isolated-drill health
```

The output contains `private/`, `data/public/`, `runtime/` package/version records and `recovery-manifest.json`. Check its expected records and schema using compatible code without exposing private contents or starting inference. A pre-migration snapshot may correctly report missing/older stores; test migration on the isolated copy if needed. The restored root contains no nested recovery snapshots, so its own recovery health can report MISSING. Validate the original snapshot separately. Keep the original snapshot unchanged during the drill.

Rollback is a coordinated offline switch of **compatible old source/build and the corresponding pre-migration data set**, not a code-only reversal. Old JSON readers would otherwise see historical files while new work remains only in SQLite. Stop writers and preserve a fresh complete snapshot of any post-migration work before reverting. Restore the chosen older snapshot into a new directory, verify it, then promote the complete compatible set during a reviewed offline cutover. Do not overwrite an open database or copy only its main file while WAL/SHM writers are active. Recovering later edits across versions requires an explicit reconciliation; stale legacy JSON is not that reconciliation.
