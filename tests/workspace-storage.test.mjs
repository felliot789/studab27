import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { once } from "node:events";
import { promises as fs, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";

const repo = fileURLToPath(new URL("..", import.meta.url));
const nativeRequire = createRequire(new URL("../package.json", import.meta.url));
const ts = nativeRequire("typescript");

// Run the actual TS storage/HTTP handlers against disposable fictional data.
// The adapter replaces only Next's response/access context; Python/SQLite run
// normally and each module context represents an independent web process.
function modules(scratch, { demo = false, deny = false } = {}) {
  const taskProcess = Object.create(process);
  taskProcess.cwd = () => scratch;
  taskProcess.env = { ...process.env, STUDAB27_DEMO: demo ? "1" : "0" };
  const context = vm.createContext({ process: taskProcess, Buffer, console, URL, Request, Response, crypto: globalThis.crypto, setTimeout, clearTimeout });
  const cache = new Map();
  class NextResponse extends Response {
    static json(value, init) { return new NextResponse(JSON.stringify(value), { ...init, headers: { "Content-Type": "application/json", ...init?.headers } }); }
  }
  function load(relative) {
    relative = path.normalize(relative);
    if (cache.has(relative)) return cache.get(relative).exports;
    const module = { exports: {} };
    cache.set(relative, module);
    const source = readFileSync(path.join(repo, relative), "utf8");
    const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
    function requireSource(name) {
      if (name === "server-only") return {};
      if (name === "next/server") return { NextResponse };
      if (name === "./access" || name === "@/lib/access") return { requireAccess: async () => { if (deny) throw new Error("Fixture access denied"); } };
      if (name === "node:child_process") return {
        execFile: (file, args, options, callback) => execFile(file, args, { ...options, env: taskProcess.env }, callback),
        spawn: (file, args, options) => spawn(file, args, { ...options, env: taskProcess.env }),
      };
      if (name.startsWith("@/")) return load("src/" + name.slice(2) + ".ts");
      if (name.startsWith(".")) return load(path.join(path.dirname(relative), name + ".ts"));
      return nativeRequire(name);
    }
    vm.runInContext("(function(exports, require, module) {" + code + "\n})", context, { filename: path.join(repo, relative) })(module.exports, requireSource, module);
    return module.exports;
  }
  return { storage: load("src/lib/storage.ts"), api: load("src/app/api/schola/route.ts"), exporter: load("src/app/api/schola/export/route.ts") };
}

async function fixture(t, overrides = {}) {
  const scratch = await fs.mkdtemp(path.join(os.tmpdir(), "studab27-storage-fictional-"));
  t.after(() => fs.rm(scratch, { recursive: true, force: true }));
  await fs.chmod(scratch, 0o700);
  await fs.mkdir(path.join(scratch, "private"), { mode: 0o700 });
  await fs.cp(path.join(repo, "data/public"), path.join(scratch, "data/public"), { recursive: true });
  await fs.symlink(path.join(repo, "schola"), path.join(scratch, "schola"), "dir");
  const profile = JSON.parse(await fs.readFile(path.join(scratch, "data/public/profile.example.json"), "utf8"));
  const overlays = JSON.parse(await fs.readFile(path.join(scratch, "data/public/overlay.example.json"), "utf8"));
  profile.mission = "fictional old generation";
  overlays[0].notes = "fictional old generation";
  const files = { profile, overlay: overlays, milestones: [], inbox: [], state: { tasks: {}, bricks: {} }, ...overrides };
  for (const [name, value] of Object.entries(files)) await fs.writeFile(path.join(scratch, "private", name + ".local.json"), JSON.stringify(value), { mode: 0o600 });
  return scratch;
}

function request(value) {
  const body = JSON.stringify(value);
  return new Request("http://127.0.0.1/api/schola", { method: "POST", headers: { "Content-Type": "application/json", "Content-Length": String(Buffer.byteLength(body)) }, body });
}
async function exported(m) {
  const response = await m.exporter.GET();
  assert.equal(response.status, 200, await response.clone().text());
  return response.json();
}
async function assertOk(response) {
  assert.equal(response.status, 200, await response.clone().text());
  assert.equal((await response.json()).ok, true);
}


test("large legal inbox export restores with retired routes, historical checklist IDs and unknown fields", async t => {
  const inbox = Array.from({ length: 400 }, (_, i) => ({ id: "fictional-note-" + i, text: "界".repeat(4000), createdAt: "2026-11-07T00:00:00Z", status: "NEW" }));
  const scratch = await fixture(t, { inbox });
  const m = modules(scratch);
  const bundle = await exported(m);
  assert.ok(Buffer.byteLength(JSON.stringify(bundle)) > 1_500_000, "Regression fixture must exceed the former restore limit");
  const retired = { ...bundle.overlays[0], routeId: "retired-fictional-scholarship", mainTarget: false, notes: "Keep retired strategy", futureField: { preserved: true } };
  bundle.overlays.push(retired);
  bundle.state.requirements = { [retired.routeId]: { "retired-guide-step": { status: "DONE", note: "Keep historical work" } } };
  await assertOk(await m.api.POST(request({ action: "import", bundle })));
  const roundtrip = await exported(m);
  assert.deepEqual(roundtrip.inbox, inbox);
  assert.deepEqual(roundtrip.overlays.find(o => o.routeId === retired.routeId), retired);
  assert.deepEqual(roundtrip.state.requirements, bundle.state.requirements);
  await assertOk(await m.api.POST(request({ action: "tracking", id: bundle.overlays[0].routeId, command: "add" })));
  assert.equal((await exported(m)).overlays.find(o => o.routeId === retired.routeId).notes, retired.notes);
});


test("independent writers return a conflict instead of losing an inbox capture", async t => {
  const scratch = await fixture(t);
  const first = modules(scratch), second = modules(scratch);
  let ready = 0, release;
  const bothLoaded = new Promise(resolve => { release = resolve; });
  for (const m of [first, second]) {
    const original = m.storage.baseData;
    m.storage.baseData = async () => {
      const base = await original();
      if (++ready === 2) release();
      await bothLoaded;
      return base;
    };
  }
  const responses = await Promise.all([
    first.api.POST(request({ action: "inbox", text: "Fictional first capture" })),
    second.api.POST(request({ action: "inbox", text: "Fictional second capture" })),
  ]);
  assert.deepEqual(responses.map(r => r.status).sort(), [200, 409]);
  assert.match((await responses.find(r => r.status === 409).json()).error, /changed the workspace/);
  const afterConflict = await exported(first);
  assert.equal(afterConflict.inbox.length, 1);
  const retry = modules(scratch);
  const missed = afterConflict.inbox[0].text.includes("first") ? "Fictional second capture" : "Fictional first capture";
  await assertOk(await retry.api.POST(request({ action: "inbox", text: missed })));
  assert.deepEqual((await exported(retry)).inbox.map(i => i.text).sort(), ["Fictional first capture", "Fictional second capture"]);
});


test("export during an uncommitted multi-table save stays on one generation", async t => {
  const scratch = await fixture(t);
  const m = modules(scratch);
  await exported(m); // Initialize the disposable workspace before the writer.
  const script = `
from pathlib import Path
import sys
from schola import workspace_store as store
root = Path.cwd()
value = store.load(root)
value['profile']['mission'] = 'fictional new generation'
value['overlays'][0]['notes'] = 'fictional new generation'
original = store._write_rows
def paused(connection, value, revision):
    waiting = True
    def trace(statement):
        nonlocal waiting
        if waiting and statement.startswith('INSERT INTO route_plans'):
            waiting = False
            print('PARTIAL_SAVE_READY', flush=True)
            sys.stdin.readline()
    connection.set_trace_callback(trace)
    original(connection, value, revision)
    connection.set_trace_callback(None)
store._write_rows = paused
store.save(root, value, value['revision'], value['mode'])
`;
  const child = spawn(process.env.SCHOLA_PYTHON || "python3", ["-c", script], { cwd: scratch, env: { ...process.env, STUDAB27_DEMO: "0" }, stdio: ["pipe", "pipe", "pipe"] });
  t.after(() => { if (child.exitCode === null) child.kill(); });
  const exited = once(child, "exit");
  let errors = "";
  child.stderr.setEncoding("utf8").on("data", value => { errors += value; });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Fictional writer did not reach the paused transaction: " + errors)), 5000);
    child.stdout.setEncoding("utf8").on("data", value => { if (value.includes("PARTIAL_SAVE_READY")) { clearTimeout(timer); resolve(); } });
    child.once("error", reject);
    child.once("exit", code => { if (code) { clearTimeout(timer); reject(new Error(errors)); } });
  });
  try {
    const during = await exported(m);
    assert.equal(during.profile.mission, "fictional old generation");
    assert.equal(during.overlays[0].notes, "fictional old generation");
  } finally { child.stdin.end("continue\n"); }
  const [code, signal] = await exited;
  assert.equal(code, 0, errors || String(signal));
  const after = await exported(m);
  assert.equal(after.profile.mission, "fictional new generation");
  assert.equal(after.overlays[0].notes, "fictional new generation");
});


test("invalid imports preserve the revision and full snapshot", async t => {
  const scratch = await fixture(t);
  const m = modules(scratch);
  const before = await exported(m);
  for (const mutate of [
    value => { value.overlays.push({ ...value.overlays[0] }); },
    value => { value.inbox = [{ id: "duplicate", text: "first", status: "NEW", createdAt: "date" }, { id: "duplicate", text: "second", status: "NEW", createdAt: "date" }]; },
    value => { value.profile.snapshot.maxFamilyContributionIdrMPerMonth = -1; },
    value => { value.state.bricks = { "fictional:item": "invalid" }; },
    value => { value.milestones = [{ title: "Impossible fictional date", date: "2026-02-30" }]; },
    value => { value.milestones = [{ title: "Impossible fictional month", date: "2026-99-99" }]; },
    value => { value.inbox = [{ id: "invalid-date", text: "Fictional note", status: "NEW", createdAt: "not-a-date" }]; },
    value => { value.schemaVersion = 999; },
  ]) {
    const bundle = structuredClone(before);
    mutate(bundle);
    const response = await m.api.POST(request({ action: "import", bundle }));
    assert.equal(response.status, 400);
    const after = await exported(m);
    delete after.exportedAt;
    const expected = structuredClone(before);
    delete expected.exportedAt;
    assert.deepEqual(after, expected);
  }
});


test("empty plans and historical rule/checklist records remain restorable", async t => {
  const scratch = await fixture(t, { overlay: [] });
  const m = modules(scratch);
  const empty = await exported(m);
  assert.deepEqual(empty.overlays, []);
  delete empty.schemaVersion; // Original v1 exports did not carry this field.
  await assertOk(await m.api.POST(request({ action: "import", bundle: empty })));
  assert.deepEqual((await exported(m)).overlays, []);
  const guides = JSON.parse(await fs.readFile(path.join(scratch, "data/public/application_guides.json"), "utf8"));
  const plans = JSON.parse(await fs.readFile(path.join(scratch, "data/public/overlay.example.json"), "utf8"));
  const plan = plans.find(p => guides[p.routeId]?.sections.some(s => s.items.some(i => !i.optional)));
  const required = guides[plan.routeId].sections.flatMap(s => s.items).find(i => !i.optional);
  plan.verifiedRules = { cycle: "2026", program: "Fictional engineering programme", sourceUrl: "https://example.edu/previous-cycle", checkedAt: "2026-01-01" };
  empty.overlays = [plan];
  empty.state.requirements = { [plan.routeId]: { [required.id]: { status: "NOT_NEEDED", note: "Historically optional before the guide changed" } } };
  await assertOk(await m.api.POST(request({ action: "import", bundle: empty })));
  const restored = await exported(m);
  assert.equal(restored.overlays[0].verifiedRules.cycle, "2026");
  assert.deepEqual(restored.state.requirements, empty.state.requirements);
  await assertOk(await m.api.POST(request({ action: "tracking", id: plan.routeId, command: "add" })));
  await assertOk(await m.api.POST(request({ action: "requirement", routeId: plan.routeId, id: required.id, note: "Updated fictional note only" })));
  const savedNote = (await exported(m)).state.requirements[plan.routeId][required.id];
  assert.equal(savedNote.status, "NOT_NEEDED", "Editing a note must preserve the historical progress decision");
  assert.equal(savedNote.note, "Updated fictional note only");
  assert.equal((await m.api.POST(request({ action: "requirement", routeId: plan.routeId, id: required.id, status: "NOT_NEEDED" }))).status, 400,
    "Retaining old evidence must not allow new invalid checklist decisions");
});


test("access checks precede data initialization and forced demo never exposes owner data", async t => {
  const scratch = await fixture(t);
  const denied = modules(scratch, { deny: true });
  assert.equal((await denied.exporter.GET()).status, 500);
  assert.equal((await denied.api.POST(request({ action: "inbox", text: "Denied capture" }))).status, 400);
  await assert.rejects(fs.stat(path.join(scratch, "private/workspace.sqlite3")), { code: "ENOENT" });
  const demo = modules(scratch, { demo: true });
  const demoBundle = await exported(demo);
  assert.equal(demoBundle.mode, "DEMO");
  assert.notEqual(demoBundle.profile.mission, "fictional old generation");
  assert.equal((await demo.api.POST(request({ action: "import", bundle: demoBundle }))).status, 400);
  await assertOk(await demo.api.POST(request({ action: "inbox", text: "Fictional demo capture" })));
  assert.equal((await exported(demo)).inbox[0].text, "Fictional demo capture");
  const owner = await exported(modules(scratch));
  assert.equal(owner.mode, "PRIVATE");
  assert.equal(owner.profile.mission, "fictional old generation");
  assert.deepEqual(owner.inbox, []);
});
