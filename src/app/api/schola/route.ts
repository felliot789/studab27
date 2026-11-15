import { NextRequest, NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { baseData, loadDashboard, python, readJson, root, saveWorkspace, serialized, vault } from "@/lib/storage";
import { type AppState, type Dashboard, type Evaluation, type InboxItem, type Task } from "@/lib/schema";
import { isoDate, number, object, text, validateOverlay, validateProfile, validateRequirementProgress } from "@/lib/validation";
import { jsonBody, IMPORT_MAX_BYTES } from "@/lib/request-body";
import { isWorkspaceView, projectDashboard } from "@/lib/dashboard-view";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const view = request.nextUrl.searchParams.get("view");
  const routeId = request.nextUrl.searchParams.get("routeId") || undefined;
  if (view !== null && !isWorkspaceView(view)) return NextResponse.json({ error: "Unknown workspace view." }, { status: 400 });
  if (view === "detail" && !routeId) return NextResponse.json({ error: "Choose a scholarship route." }, { status: 400 });
  try {
    const data = await loadDashboard();
    if (view === "detail" && !data.routes.some(route => route.id === routeId)) return NextResponse.json({ error: "Scholarship route not found." }, { status: 404 });
    return NextResponse.json(view === null ? data : projectDashboard(data, view, routeId));
  }
  catch { return NextResponse.json({ error: "Could not load local data. Existing vault files were preserved; inspect the local server log." }, { status: 500 }); }
}

export async function POST(request: NextRequest) {
  try {
    const input = await jsonBody(request, IMPORT_MAX_BYTES);
    if (input.action === "simulate") {
      const base = await baseData();
      const sat = number(input.sat, 1350, 1560), cap = number(input.cap, 0, 100);
      if (!Number.isInteger(sat)) throw new Error("SAT score must be a whole number.");
      return NextResponse.json({ evaluations: await python<Evaluation[]>("schola.evaluator", { routes: base.routes, profile: base.profile, overlays: base.overlays, sat, cap }) });
    }
    return await serialized(async () => {
      const base = await baseData();
      const state: AppState = base.workspace.state;
      const now = new Date().toISOString();
      switch (input.action) {
        case "requirement": {
          const routeId = text(input.routeId, 150), id = text(input.id, 100);
          const prior = state.requirements?.[routeId]?.[id];
          const progress = { status: input.status, note: input.note === undefined ? prior?.note || "" : input.note, updatedAt: now };
          const checked = validateRequirementProgress({ [routeId]: { [id]: { ...progress, status: input.status === undefined ? "TODO" : input.status } } }, base.routes);
          if (input.status === undefined && prior) checked[routeId][id].status = prior.status;
          state.requirements = { ...state.requirements, [routeId]: { ...state.requirements?.[routeId], ...checked[routeId] } };
          break;
        }
        case "tracking": {
          const id = text(input.id, 150), command = text(input.command, 30);
          if (!base.routes.some(route => route.id === id) || !base.overlays.some(o => o.routeId === id) || !["add", "remove", "main"].includes(command)) throw new Error("Unknown tracker action.");
          const updated = base.overlays.map(o => o.routeId === id
            ? { ...o, tracked: command !== "remove", mainTarget: command === "main" || (command === "add" && !!o.mainTarget), pursuitLevel: command === "main" ? "FOCUS" : o.pursuitLevel }
            : command === "main" ? { ...o, mainTarget: false } : o);
          const ids = new Set(base.routes.map(r => r.id));
          validateOverlay(updated.find(o => o.routeId === id), ids, true);
          await saveWorkspace(base.workspace, { overlays: updated });
          return NextResponse.json({ ok: true });
        }
        case "task": {
          const id = text(input.id, 100), command = text(input.command, 30);
          const tasks = await python<Task[]>("schola.spoonfeeder", { tasks: base.tasks, routes: base.routes, profile: base.profile, overlays: base.overlays, bricks: base.bricks, milestones: base.milestones, command: "pool" });
          if (!tasks.some(t => t.id === id)) throw new Error("Unknown briefing task.");
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
          const allowed = ["applicationStatus", "personalStrategyTier", "costEstimate", "notes", "verifiedRules", "saved", "pursuitLevel"];
          if (Object.keys(patch).some(k => !allowed.includes(k))) throw new Error("Unsupported route field.");
          const candidate = { ...existing, ...patch };
          if ("pursuitLevel" in patch && patch.pursuitLevel !== "FOCUS") candidate.mainTarget = false;
          if (patch.pursuitLevel === null) delete candidate.pursuitLevel;
          if (patch.costEstimate === null) delete candidate.costEstimate;
          const updated = validateOverlay(candidate, new Set(base.routes.map(r => r.id)), patch.verifiedRules === undefined);
          await saveWorkspace(base.workspace, { overlays: base.overlays.map(o => o.routeId === id ? updated : o) });
          return NextResponse.json({ ok: true });
        }
        case "inbox": {
          const captured = text(input.text, 4000).trim();
          if (!captured) throw new Error("Add a link or note first.");
          const inbox: InboxItem[] = base.workspace.inbox;
          if (inbox.length >= 500) throw new Error("Inbox has 500 items; triage or export before adding more.");
          inbox.unshift({ id: crypto.randomUUID(), text: captured, createdAt: now, status: "NEW" });
          await saveWorkspace(base.workspace, { inbox });
          return NextResponse.json({ ok: true });
        }
        case "triage": {
          const id = text(input.id, 100);
          if (!["NEW", "TRIAGED"].includes(String(input.status))) throw new Error("Unknown inbox status.");
          const inbox: InboxItem[] = base.workspace.inbox;
          if (!inbox.some(i => i.id === id)) throw new Error("Unknown inbox item.");
          await saveWorkspace(base.workspace, { inbox: inbox.map(i => i.id === id ? { ...i, status: input.status as InboxItem["status"] } : i) });
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
          if (bundle.format !== "studab27-v1" || (bundle.schemaVersion !== undefined && bundle.schemaVersion !== 1)) throw new Error("Unsupported export format.");
          const profile = validateProfile(bundle.profile);
          if (!Array.isArray(bundle.overlays)) throw new Error("Import must include scholarship route plans.");
          const ids = new Set(bundle.overlays.map(v => text(object(v).routeId, 150)));
          const overlays = bundle.overlays.map(v => validateOverlay(v, ids, true));
          if (ids.size !== overlays.length) throw new Error("Duplicate route overlays.");
          if (overlays.filter(o => o.mainTarget).length > 1) throw new Error("Choose one main target.");
          if (!Array.isArray(bundle.milestones) || !Array.isArray(bundle.inbox)) throw new Error("Milestones and inbox arrays are required.");
          for (const raw of bundle.milestones) {
            const m = object(raw); text(m.title, 1000);
            isoDate(m.date);
          }
          if (bundle.inbox.length > 500) throw new Error("Too many inbox items.");
          for (const raw of bundle.inbox) {
            const i = object(raw); text(i.id, 100); text(i.text, 4000); text(i.createdAt, 100);
            if (!Number.isFinite(Date.parse(i.createdAt as string))) throw new Error("Invalid inbox date.");
            if (!["NEW", "TRIAGED"].includes(String(i.status))) throw new Error("Invalid inbox status.");
          }
          const importedState = object(bundle.state);
          const taskStates = object(importedState.tasks), brickStates = object(importedState.bricks);
          if (importedState.requirements !== undefined) validateRequirementProgress(importedState.requirements, base.routes, ids);
          for (const [id, value] of Object.entries(taskStates)) {
            text(id, 100);
            const entry = object(value);
            if (entry.status !== undefined && entry.status !== "DONE") throw new Error("Invalid task status.");
            for (const key of ["snoozedUntil", "replacedAt"]) if (entry[key] !== undefined && !Number.isFinite(Date.parse(String(entry[key])))) throw new Error("Invalid task date.");
          }
          for (const [key, done] of Object.entries(brickStates)) { text(key, 100); if (typeof done !== "boolean") throw new Error("Invalid document checklist."); }
          await saveWorkspace(base.workspace, { profile, overlays, milestones: bundle.milestones as typeof base.milestones, inbox: bundle.inbox as InboxItem[], state: importedState as AppState }, true);
          return NextResponse.json({ ok: true });
        }
        default: throw new Error("Unknown Schola action.");
      }
      state.updatedAt = now;
      await saveWorkspace(base.workspace, { state });
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Request failed; local files were preserved.";
    return NextResponse.json({ error: message }, { status: error && typeof error === "object" && "conflict" in error && error.conflict ? 409 : 400 });
  }
}
