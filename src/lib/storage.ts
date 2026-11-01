import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { AppState, Brick, Dashboard, Evaluation, InboxItem, Milestone, Overlay, Profile, Route, SourceNote, Task, WatchState } from "./schema";

const run = promisify(execFile);
export const root = process.cwd();
export const vault = path.join(root, "private");
const publicDir = path.join(root, "data/public");

export async function readJson<T>(filename: string, fallback?: T): Promise<T> {
  try { return JSON.parse(await fs.readFile(filename, "utf8")) as T; }
  catch (e) { if ((e as NodeJS.ErrnoException).code === "ENOENT" && fallback !== undefined) return fallback; throw new Error(`Cannot read ${path.basename(filename)}; existing data was preserved.`); }
}

export async function writeJson(filename: string, value: unknown) {
  await fs.mkdir(vault, { recursive: true, mode: 0o700 });
  const temp = `${filename}.${process.pid}.tmp`;
  await fs.writeFile(temp, JSON.stringify(value, null, 2) + "\n", { mode: 0o600 });
  await fs.chmod(temp, 0o600);
  await fs.rename(temp, filename);
}

export async function mode() {
  if (process.env.STUDAB27_DEMO === "1") return "DEMO" as const;
  const exists = await Promise.all(["profile", "overlay"].map(async n => { try { await fs.access(path.join(vault, `${n}.local.json`)); return true; } catch { return false; } }));
  if (exists.some(Boolean) && !exists.every(Boolean)) throw new Error("The private vault is incomplete. Restore both profile and overlay; personal and demo records were not mixed.");
  return exists.every(Boolean) ? "PRIVATE" as const : "DEMO" as const;
}

export async function python<T>(module: string, payload: unknown): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const child = execFile(/* turbopackIgnore: true */ process.env.SCHOLA_PYTHON || "python3", ["-m", module], { cwd: root, maxBuffer: 8 * 1024 * 1024, timeout: 15000 }, (error, stdout) => {
      if (error) { reject(new Error("Schola could not evaluate this request. Check the local Python runtime; no eligibility was inferred.")); return; }
      try { resolve(JSON.parse(stdout)); } catch { reject(new Error("Schola returned an invalid result.")); }
    });
    child.stdin?.on("error", () => {});
    child.stdin?.end(JSON.stringify(payload));
  });
}

export async function baseData() {
  const currentMode = await mode();
  const [routes, profile, overlays, templates, bricks, sourceNotes, milestones] = await Promise.all([
    readJson<Route[]>(path.join(publicDir, "scholarships_2027.json")),
    readJson<Profile>(currentMode === "PRIVATE" ? path.join(vault, "profile.local.json") : path.join(publicDir, "profile.example.json")),
    currentMode === "PRIVATE" ? readJson<Overlay[]>(path.join(vault, "overlay.local.json")) : readJson<Overlay[]>(path.join(vault, "demo-overlay.local.json"), await readJson<Overlay[]>(path.join(publicDir, "overlay.example.json"))),
    readJson<Task[]>(path.join(publicDir, "tasks.json")), readJson<Brick[]>(path.join(publicDir, "bricks.json")), readJson<SourceNote[]>(path.join(publicDir, "source_verifications.json")),
    currentMode === "PRIVATE" ? readJson<Milestone[]>(path.join(vault, "milestones.local.json"), []) : Promise.resolve([]),
  ]);
  const tasks = await python<Task[]>("schola.spoonfeeder", { tasks: templates, routes, profile, overlays, bricks, milestones, command: "pool" });
  return { mode: currentMode, routes, profile, overlays, tasks, bricks, sourceNotes, milestones };
}

export const statePath = (currentMode: "PRIVATE" | "DEMO") => path.join(vault, currentMode === "PRIVATE" ? "state.local.json" : "demo-state.local.json");
export const inboxPath = (currentMode: "PRIVATE" | "DEMO") => path.join(vault, currentMode === "PRIVATE" ? "inbox.local.json" : "demo-inbox.local.json");
export const emptyState = (): AppState => ({ tasks: {}, bricks: {} });

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
  const [state, inbox, watch, schedule] = await Promise.all([
    readJson<AppState>(statePath(base.mode), emptyState()),
    readJson<InboxItem[]>(inboxPath(base.mode), []),
    readJson<WatchState>(path.join(vault, "watchtower_state.local.json"), await readJson<WatchState>(path.join(publicDir, "watchtower_state.json"))),
    scheduleStatus(),
  ]);
  const payload = { ...base, state };
  const [evaluations, briefing] = await Promise.all([python<Evaluation[]>("schola.evaluator", payload), python<Dashboard["briefing"]>("schola.spoonfeeder", payload)]);
  const { tasks: _tasks, ...data } = base;
  return { ...data, evaluations, briefing, state, inbox, watch, schedule };
}

// ponytail: one local process serializes writes. Use SQLite if multiple app workers are needed.
const globalQueue = globalThis as typeof globalThis & { studabQueue?: Promise<unknown> };
export async function serialized<T>(operation: () => Promise<T>): Promise<T> {
  const result = (globalQueue.studabQueue || Promise.resolve()).then(operation);
  globalQueue.studabQueue = result.catch(() => {});
  return result;
}
