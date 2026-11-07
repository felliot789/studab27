import { NextRequest, NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { requireAccess } from "@/lib/access";
import { jsonBody } from "@/lib/request-body";
import { mode } from "@/lib/storage";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function assistant(payload: unknown): Promise<Record<string, unknown>> {
  const currentMode = await mode();
  return new Promise((resolve, reject) => {
    const child = execFile(/* turbopackIgnore: true */ process.env.SCHOLA_PYTHON || "python3", ["-m", "schola.assistant", "api"], { cwd: process.cwd(), timeout: 10000, maxBuffer: 3 * 1024 * 1024, env: { ...process.env, STUDAB27_DEMO: currentMode === "DEMO" ? "1" : "0" } }, (error, stdout) => {
      if (error) { reject(new Error("Schola’s local conversation store is unavailable. Your existing messages are preserved.")); return; }
      try { resolve(JSON.parse(stdout)); } catch { reject(new Error("Schola could not read this conversation.")); }
    });
    child.stdin?.on("error", () => {});
    child.stdin?.end(JSON.stringify(payload));
  });
}
export async function GET(request: NextRequest) {
  await requireAccess();
  try {
    const value = await assistant({ action: "status", routeId: request.nextUrl.searchParams.get("routeId") });
    return NextResponse.json(value, { status: value.error ? 400 : 200 });
  } catch (error) { return NextResponse.json({ error: (error as Error).message }, { status: 503 }); }
}
export async function POST(request: NextRequest) {
  await requireAccess();
  try {
    const value = await assistant(await jsonBody(request, 30000));
    return NextResponse.json(value, { status: value.error ? 400 : 202 });
  } catch (error) { return NextResponse.json({ error: (error as Error).message }, { status: 400 }); }
}
