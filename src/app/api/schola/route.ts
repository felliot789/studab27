import { NextRequest, NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { baseData, emptyState, inboxPath, loadDashboard, python, readJson, root, serialized, statePath, vault, writeJson } from "@/lib/storage";
import { type AppState, type Dashboard, type Evaluation, type InboxItem, type Task } from "@/lib/schema";
import { assertSafeKeys, number, object, text, validateOverlay, validateProfile } from "@/lib/validation";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try { return NextResponse.json(await loadDashboard()); }
  catch { return NextResponse.json({ error: "Could not load local data. Existing vault files were preserved; inspect the local server log." }, { status: 500 }); }
}

async function body(request: NextRequest) {
  const size = Number(request.headers.get("content-length") || 0);
  if (size > 1_500_000) throw new Error("JSON import is too large.");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("A JSON request is required.");
  let total = 0;
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > 1_500_000) { await reader.cancel(); throw new Error("JSON import is too large."); }
    chunks.push(value);
  }
  const parsed: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  assertSafeKeys(parsed);
  return object(parsed);
}

export async function POST(request: NextRequest) {
  try {
    const input = await body(request);
    if (input.action === "simulate") {
      const base = await baseData();
      const sat = number(input.sat, 1350, 1560), cap = number(input.cap, 0, 100);
      if (!Number.isInteger(sat)) throw new Error("SAT score must be a whole number.");
      return NextResponse.json({ evaluations: await python<Evaluation[]>("schola.evaluator", { ...base, sat, cap }) });
    }
    return await serialized(async () => {
      const base = await baseData();
      const state = await readJson<AppState>(statePath(base.mode), emptyState());
      const now = new Date().toISOString();
      switch (input.action) {
        case "task": {
          const id = text(input.id, 100), command = text(input.command, 30);
          if (!base.tasks.some(t => t.id === id)) throw new Error("Unknown briefing task.");
          const prior = state.tasks[id] || {};
          if (command === "done") state.tasks[id] = { ...prior, status: "DONE" };
          else if (command === "snooze") state.tasks[id] = { ...prior, snoozedUntil: new Date(Date.now() + 86400000).toISOString() };
          else if (command === "replace") state.tasks[id] = { ...prior, replacedAt: now };
          else if (command === "undo") state.tasks[id] = {};
          else throw new Error("Unknown task action.");
          break;
        }
        case "brick": {
          const key = text(input.key, 100);
          if (!base.bricks.some(b => b.items.some(i => `${b.id}:${i.id}` === key)) || typeof input.done !== "boolean") throw new Error("Unknown document step.");
          state.bricks[key] = input.done;
          break;
        }
        case "overlay": {
          const id = text(input.id, 150);
          const existing = base.overlays.find(o => o.routeId === id);
          if (!existing) throw new Error("Unknown scholarship route.");
          const patch = object(input.patch);
          const allowed = ["applicationStatus", "personalStrategyTier", "costEstimate", "notes", "verifiedRules"];
          if (Object.keys(patch).some(k => !allowed.includes(k))) throw new Error("Unsupported route field.");
          const candidate = { ...existing, ...patch };
          if (patch.costEstimate === null) delete candidate.costEstimate;
          const updated = validateOverlay(candidate, new Set(base.routes.map(r => r.id)));
          // Demo edits live separately and cannot modify the public fictional preset.
          const destination = path.join(vault, base.mode === "PRIVATE" ? "overlay.local.json" : "demo-overlay.local.json");
          await writeJson(destination, base.overlays.map(o => o.routeId === id ? updated : o));
          return NextResponse.json({ ok: true });
        }
        case "inbox": {
          const captured = text(input.text, 4000).trim();
          if (!captured) throw new Error("Add a link or note first.");
          const inbox = await readJson<InboxItem[]>(inboxPath(base.mode), []);
          if (inbox.length >= 500) throw new Error("Inbox has 500 items; triage or export before adding more.");
          inbox.unshift({ id: crypto.randomUUID(), text: captured, createdAt: now, status: "NEW" });
          await writeJson(inboxPath(base.mode), inbox);
          return NextResponse.json({ ok: true });
        }
        case "triage": {
          const id = text(input.id, 100);
          if (!["NEW", "TRIAGED"].includes(String(input.status))) throw new Error("Unknown inbox status.");
          const inbox = await readJson<InboxItem[]>(inboxPath(base.mode), []);
          if (!inbox.some(i => i.id === id)) throw new Error("Unknown inbox item.");
          await writeJson(inboxPath(base.mode), inbox.map(i => i.id === id ? { ...i, status: input.status as InboxItem["status"] } : i));
          return NextResponse.json({ ok: true });
        }
        case "scan": {
          const watch = await readJson<Dashboard["watch"]>(path.join(vault, "watchtower_state.local.json"), { lastRunAt: null, sources: {}, events: [] });
          if (watch.running && Date.now() - Date.parse(watch.runStartedAt || "") < 30 * 60 * 1000) throw new Error("A source scan is already running.");
          const logPath = path.join(vault, "watchtower.local.log");
          await fs.mkdir(vault, { recursive: true, mode: 0o700 });
          const log = await fs.open(logPath, "a", 0o600);
          try {
            const child = spawn(/* turbopackIgnore: true */ process.env.SCHOLA_PYTHON || "python3", ["-m", "schola.watcher"], { cwd: root, detached: true, stdio: ["ignore", log.fd, log.fd] });
            await new Promise<void>((resolve, reject) => { child.once("spawn", resolve); child.once("error", reject); });
            child.unref();
          } finally { await log.close(); }
          return NextResponse.json({ ok: true, message: "Scan started. Results will appear as sources finish." }, { status: 202 });
        }
        case "import": {
          if (process.env.STUDAB27_DEMO === "1") throw new Error("Import is disabled while demo mode is forced.");
          const bundle = object(input.bundle);
          if (bundle.format !== "studab27-v1") throw new Error("Unsupported export format.");
          const profile = validateProfile(bundle.profile);
          if (!Array.isArray(bundle.overlays) || bundle.overlays.length !== base.routes.length) throw new Error("Import must include all catalogue overlays.");
          const ids = new Set(base.routes.map(r => r.id));
          const overlays = bundle.overlays.map(v => validateOverlay(v, ids));
          if (new Set(overlays.map(o => o.routeId)).size !== ids.size) throw new Error("Duplicate or missing route overlays.");
          if (!Array.isArray(bundle.milestones) || !Array.isArray(bundle.inbox)) throw new Error("Milestones and inbox arrays are required.");
          for (const raw of bundle.milestones) {
            const m = object(raw); text(m.title, 1000);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(text(m.date, 10))) throw new Error("Invalid milestone date.");
          }
          if (bundle.inbox.length > 500) throw new Error("Too many inbox items.");
          for (const raw of bundle.inbox) {
            const i = object(raw); text(i.id, 100); text(i.text, 4000); text(i.createdAt, 100);
            if (!["NEW", "TRIAGED"].includes(String(i.status))) throw new Error("Invalid inbox status.");
          }
          const importedState = object(bundle.state);
          const taskStates = object(importedState.tasks), brickStates = object(importedState.bricks);
          const importedTasks = await python<Task[]>("schola.spoonfeeder", { ...base, tasks: base.tasks.filter(t => !t.generated), profile, overlays, milestones: bundle.milestones, command: "pool" });
          for (const [id, value] of Object.entries(taskStates)) {
            if (!importedTasks.some(t => t.id === id)) throw new Error("Unknown imported task.");
            const entry = object(value);
            if (entry.status !== undefined && entry.status !== "DONE") throw new Error("Invalid task status.");
            for (const key of ["snoozedUntil", "replacedAt"]) if (entry[key] !== undefined && !Number.isFinite(Date.parse(String(entry[key])))) throw new Error("Invalid task date.");
          }
          for (const [key, done] of Object.entries(brickStates)) if (typeof done !== "boolean" || !base.bricks.some(b => b.items.some(i => `${b.id}:${i.id}` === key))) throw new Error("Invalid document checklist.");
          const files = { "profile.local.json": profile, "overlay.local.json": overlays, "milestones.local.json": bundle.milestones, "inbox.local.json": bundle.inbox, "state.local.json": importedState };
          // Keep a complete pre-import recovery bundle before touching existing files.
          const backup: Record<string, unknown> = {};
          for (const name of Object.keys(files)) backup[name] = await readJson<unknown>(path.join(vault, name), null);
          const backupDir = path.join(vault, "backups");
          await fs.mkdir(backupDir, { recursive: true, mode: 0o700 });
          await writeJson(path.join(backupDir, `before-import-${Date.now()}.local.json`), backup);
          try {
            for (const [name, value] of Object.entries(files)) await writeJson(path.join(vault, name), value);
          } catch {
            for (const [name, value] of Object.entries(backup)) {
              if (value === null) await fs.rm(path.join(vault, name), { force: true });
              else await writeJson(path.join(vault, name), value);
            }
            throw new Error("Import failed; previous data was restored from the recovery bundle.");
          }
          return NextResponse.json({ ok: true });
        }
        default: throw new Error("Unknown Schola action.");
      }
      state.updatedAt = now;
      await writeJson(statePath(base.mode), state);
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Request failed; local files were preserved.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
