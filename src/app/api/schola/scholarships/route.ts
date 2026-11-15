import { NextRequest, NextResponse } from "next/server";
import { requireAccess } from "@/lib/access";
import { jsonBody } from "@/lib/request-body";
import { python, serialized } from "@/lib/storage";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function handle(payload: unknown) {
  const result = await serialized(() => python<Record<string, unknown>>("schola.catalogue_api", payload));
  return NextResponse.json(result, { status: result.error ? (result.conflict ? 409 : 400) : 200, headers: { "Cache-Control": "no-store, private" } });
}
export async function GET() {
  await requireAccess();
  try { return await handle({ action: "list" }); }
  catch { return NextResponse.json({ error: "Scholarship drafts are unavailable. Saved records were preserved." }, { status: 503 }); }
}
export async function POST(request: NextRequest) {
  await requireAccess();
  try { return await handle(await jsonBody(request, 100000)); }
  catch (error) { return NextResponse.json({ error: (error as Error).message }, { status: 400 }); }
}
