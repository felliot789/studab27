import { NextResponse } from "next/server";
import { baseData, emptyState, inboxPath, readJson, statePath, vault } from "@/lib/storage";
import path from "node:path";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const base = await baseData();
    const [state, inbox, milestones] = await Promise.all([
      readJson(statePath(base.mode), emptyState()), readJson(inboxPath(base.mode), []),
      base.mode === "PRIVATE" ? readJson(path.join(vault, "milestones.local.json"), []) : Promise.resolve([]),
    ]);
    const bundle = { format: "studab27-v1", exportedAt: new Date().toISOString(), mode: base.mode, profile: base.profile, overlays: base.overlays, state, milestones, inbox };
    return new NextResponse(JSON.stringify(bundle, null, 2), { headers: { "Content-Type": "application/json", "Content-Disposition": `attachment; filename="studab27-${new Date().toISOString().slice(0, 10)}.local.json"`, "Cache-Control": "no-store, private" } });
  } catch { return NextResponse.json({ error: "Export failed; vault files were preserved." }, { status: 500 }); }
}
