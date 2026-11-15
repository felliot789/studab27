import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { ApplicationGuide, AppState, Brick, CalendarEvent, Dashboard, InboxItem, Milestone, Overlay, Profile, Route, ScholarshipOutlook, SourceNote, Task, WatchState } from "./schema";
import { requireAccess } from "./access";

const run = promisify(execFile);
export const root = process.cwd();
export const vault = path.join(root, "private");
const publicDir = path.join(root, "data/public");

export async function readJson<T>(filename: string, fallback?: T): Promise<T> {
  try { return JSON.parse(await fs.readFile(filename, "utf8")) as T; }
  catch (e) { if ((e as NodeJS.ErrnoException).code === "ENOENT" && fallback !== undefined) return fallback; throw new Error(`Cannot read ${path.basename(filename)}; existing data was preserved.`); }
}

export type WorkspaceSnapshot = { mode: "PRIVATE" | "DEMO"; revision: number; profile: Profile; overlays: Overlay[]; milestones: Milestone[]; state: AppState; inbox: InboxItem[] };
export async function loadWorkspace(): Promise<WorkspaceSnapshot> {
  const value = await python<WorkspaceSnapshot & { error?: string }>("schola.workspace_store", { action: "load" });
  if (value.error) throw new Error(value.error);
  return value;
}
export async function mode() { return (await loadWorkspace()).mode; }
export async function saveWorkspace(workspace: WorkspaceSnapshot, changes: Partial<WorkspaceSnapshot>, imported = false) {
  const value = await python<{ error?: string; conflict?: boolean }>("schola.workspace_store", {
    action: "save", revision: workspace.revision, mode: workspace.mode,
    workspace: { ...workspace, ...changes }, targetMode: imported ? "PRIVATE" : workspace.mode, backup: imported,
  });
  if (value.error) throw Object.assign(new Error(value.error), { conflict: !!value.conflict });
}

export async function python<T>(module: string, payload: unknown): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const child = execFile(/* turbopackIgnore: true */ process.env.SCHOLA_PYTHON || "python3", ["-m", module], { cwd: root, maxBuffer: 32 * 1024 * 1024, timeout: 15000 }, (error, stdout) => {
      if (error) { reject(new Error("Schola could not evaluate this request. Check the local Python runtime; no eligibility was inferred.")); return; }
      try { resolve(JSON.parse(stdout)); } catch { reject(new Error("Schola returned an invalid result.")); }
    });
    child.stdin?.on("error", () => {});
    child.stdin?.end(JSON.stringify(payload));
  });
}

export async function baseData() {
  await requireAccess();
  const workspace = await loadWorkspace();
  const [catalogue, templates, bricks, sourceNotes, calendarEvents, outlooks, guides] = await Promise.all([
    readJson<Route[]>(path.join(publicDir, "scholarships_2027.json")),
    readJson<Task[]>(path.join(publicDir, "tasks.json")), readJson<Brick[]>(path.join(publicDir, "bricks.json")), readJson<SourceNote[]>(path.join(publicDir, "source_verifications.json")),
    readJson<CalendarEvent[]>(path.join(publicDir, "calendar_events.json")),
    readJson<Record<string, ScholarshipOutlook>>(path.join(publicDir, "scholarship_outlooks.json"), {}),
    readJson<Record<string, ApplicationGuide>>(path.join(publicDir, "application_guides.json"), {}),
  ]);
  const { mode: currentMode, profile, milestones } = workspace;
  const overlays = [...workspace.overlays];
  for (const route of catalogue) if (!overlays.some(plan => plan.routeId === route.id)) overlays.push({ routeId: route.id, applicationStatus: "NOT_STARTED", personalStrategyTier: "", estimatedFamilyGapIdrMPerMonth: "", personalSatTargetNote: "", personalRiskNote: "" });
  workspace.overlays = overlays;
  const local = currentMode === "PRIVATE" ? Object.values(workspace.state.localScholarships || {}) : [];
  const routes = [...catalogue, ...local].map(route => ({ ...route, scholarshipOutlook: outlooks[route.id], applicationGuide: guides[route.id] }));
  for (const route of local) if (!overlays.some(plan => plan.routeId === route.id)) overlays.push({ routeId: route.id, applicationStatus: "NOT_STARTED", personalStrategyTier: "", estimatedFamilyGapIdrMPerMonth: "", personalSatTargetNote: "", personalRiskNote: "" });
  return { mode: currentMode, routes, profile, overlays, tasks: templates, bricks, sourceNotes, milestones, calendarEvents, workspace };
}

export async function scheduleStatus() {
  const runtimeDir = process.env.XDG_RUNTIME_DIR || `/run/user/${process.getuid?.()}`;
  const env = { ...process.env, XDG_RUNTIME_DIR: runtimeDir, DBUS_SESSION_BUS_ADDRESS: process.env.DBUS_SESSION_BUS_ADDRESS || `unix:path=${runtimeDir}/bus` };
  try {
    const { stdout } = await run("systemctl", ["--user", "is-active", "studab27-watchtower.timer"], { timeout: 2500, env });
    if (stdout.trim() === "active") {
      const { stdout: next } = await run("systemctl", ["--user", "show", "studab27-watchtower.timer", "--property=NextElapseUSecRealtime", "--value"], { timeout: 2500, env });
      return { active: true, label: "12-hour local timer active", nextRunAt: next.trim() || undefined };
    }
  } catch { /* An inactive/unavailable scheduler is not a running agent. */ }
  return { active: false, label: "Manual scans · schedule not active" };
}

export async function loadDashboard(): Promise<Dashboard> {
  const base = await baseData();
  const { state, inbox } = base.workspace;
  const { routes, profile, overlays, tasks, bricks, milestones } = base;
  const [watch, schedule, derived] = await Promise.all([
    readJson<WatchState>(path.join(vault, "watchtower_state.local.json"), await readJson<WatchState>(path.join(publicDir, "watchtower_state.json"))),
    scheduleStatus(),
    python<Pick<Dashboard, "evaluations" | "briefing">>("schola.dashboard", { routes, profile, overlays, tasks, bricks, milestones, state }),
  ]);
  const { tasks: _tasks, workspace: _workspace, ...data } = base;
  return { ...data, ...derived, state, inbox, watch, schedule };
}

// SQLite revision checks coordinate independent processes; this queue avoids avoidable local conflicts.
const globalQueue = globalThis as typeof globalThis & { studabQueue?: Promise<unknown> };
export async function serialized<T>(operation: () => Promise<T>): Promise<T> {
  const result = (globalQueue.studabQueue || Promise.resolve()).then(operation);
  globalQueue.studabQueue = result.catch(() => {});
  return result;
}
