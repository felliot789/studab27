import { NextResponse } from "next/server";
import { requireAccess } from "@/lib/access";
import { loadWorkspace } from "@/lib/storage";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await requireAccess();
    const { revision, ...workspace } = await loadWorkspace();
    const bundle = { format: "studab27-v1", schemaVersion: 1, exportedAt: new Date().toISOString(), revision, ...workspace };
    return new NextResponse(JSON.stringify(bundle), { headers: { "Content-Type": "application/json", "Content-Disposition": `attachment; filename="studab27-${new Date().toISOString().slice(0, 10)}.local.json"`, "Cache-Control": "no-store, private" } });
  } catch { return NextResponse.json({ error: "Export failed; workspace records were preserved." }, { status: 500 }); }
}
