# StudAb27

## Privacy first

- Public code, catalogue, and fictional demo data are safe to commit. Real profiles, route strategy, milestones, task history, inbox captures, exports, and downloaded documents belong only in the ignored `private/` vault.
- Never copy the original project seed into tracked files: it combines public and private information.
- Install the privacy hook with `python3 scripts/install-hooks.py` before committing. Run `npm run check` before a handoff. Inspect staged content as well as paths.
- Read private files at request time on the server only. Never import them into client bundles or prerender private pages. Bind this unauthenticated personal app to loopback.
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

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
