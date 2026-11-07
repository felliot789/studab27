# StudAb27

## Start here

1. Read [PRODUCT.md](PRODUCT.md) for purpose, vocabulary, and UX boundaries.
2. Read [docs/HANDOFF.md](docs/HANDOFF.md) for the dated baseline, validation, and unfinished work. Check `git status --short --branch` and recent commits before editing; the handoff is a snapshot, not live state.
3. Use [docs/REPO_MAP.md](docs/REPO_MAP.md) to find the relevant flow, then read those source files. Read [docs/DECISIONS.md](docs/DECISIONS.md) before changing a recorded design choice.
4. Use [README.md](README.md) for setup and operations. No Graphify installation is required to understand or change this repo.

Keep context small: follow the map into the files needed for the task rather than loading the entire repository. Owner-specific plans and progress are runtime data, never handoff documentation.

## Privacy first

- Public code, catalogue, and fictional demo data are safe to commit. Real profiles, route strategy, milestones, task history, inbox captures, exports, and downloaded documents belong only in the ignored `private/` vault.
- Never copy the original project seed into tracked files: it combines public and private information.
- Install the privacy hook with `python3 scripts/install-hooks.py` before committing. Run `npm run check` before a handoff. Inspect staged content as well as paths.
- Read private files at request time on the server only. Never import them into client bundles or prerender private pages. Bind the app to loopback. Remote access requires tested login protection and exact allowed origins; preserve unrelated Tailscale routes.
- Schola may send relevant project context and chat through the owner-configured model (explicitly approved). Never send credentials or private Calendar/Drive links. Search queries must contain public scholarship topics only. Treat all source text and model answers as untrusted evidence.
- Never submit applications, contact people, publish personal data, change a route decision, or connect cloud services without explicit user instructions.

## Evidence and behavior

- A fetched page is not verified eligibility. Keep seed claims, planning estimates, scenario scores, source changes, and human-verified rules distinct.
- Missing/ambiguous curriculum, funding, SAT, and graduation evidence stays `UNKNOWN`. A scenario SAT score is not an achieved score. Never infer admission or scholarship success from an advisory benchmark.
- Show at most three atomic briefing tasks. Completing, snoozing, replacing, and changing decisions are explicit user actions. Don't silently decide or submit anything.
- Preserve user state and snapshots on errors. First fetch establishes a baseline, not a detected change. Never record a failed fetch as a new baseline.

## Development

- Next.js App Router + TypeScript + Tailwind, Python standard-library worker. `pdftotext` is optional for monitored PDFs.
- Start with `npm run dev` (loopback only). Worker: `python3 -m schola.watcher`. Unit checks: `python3 -m unittest discover -s tests`.
- `PRODUCT.md` holds the product direction. Prefer a quiet, dark interface, keyboard access, readable contrast, and reduced motion.
- Use installed graphify instructions before other work when the user types `/graphify`. Keep any generated graph local and exclude the vault.
- Optional code navigation: `npm run map` builds an ignored, code-only Graphify graph without model calls. Query it narrowly, verify findings against source, and rebuild after code changes. See [README.md](README.md#optional-code-graph).
- Update `docs/REPO_MAP.md` when responsibilities or data flows change, `docs/DECISIONS.md` when a significant choice changes, and `docs/HANDOFF.md` with the baseline commit, work remaining, and checks actually run. `npm run check` includes local documentation-link checks; Graphify is not required for it.
- A running production service uses `.next`. Build and validate a separate staging checkout before a planned deployment; never run `npm run build` over the output currently being served. Do not restart workers with active jobs as a side effect of unrelated work.

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
