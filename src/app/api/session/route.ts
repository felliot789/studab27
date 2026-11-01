import { NextRequest, NextResponse } from "next/server";
import { accessSettings, checkPassword, newSession, sessionCookie, trustedOrigin } from "@/lib/access";
import { jsonBody } from "@/lib/request-body";

export const runtime = "nodejs";
const state = globalThis as typeof globalThis & { studabLogin?: { since: number; failures: number } };
export async function POST(request: NextRequest) {
  try {
    const settings = await accessSettings();
    const origin = trustedOrigin((request.headers.get("host") || "").toLowerCase(), settings);
    if (!origin || request.headers.get("origin") !== origin) return NextResponse.json({ error: "Same-origin login is required." }, { status: 403 });
    if (!settings.enabled) return NextResponse.json({ error: "Login is not configured." }, { status: 503 });
    const input = await jsonBody(request, 2000);
    const response = NextResponse.json({ ok: true });
    if (input.action === "logout") {
      response.cookies.set(sessionCookie, "", { httpOnly: true, secure: origin.startsWith("https:"), sameSite: "strict", path: "/", maxAge: 0 });
      return response;
    }
    const attempts = state.studabLogin;
    if (!attempts || Date.now() - attempts.since > 15 * 60000) state.studabLogin = { since: Date.now(), failures: 0 };
    if (state.studabLogin!.failures >= 15) return NextResponse.json({ error: "Too many failed logins. Try again in 15 minutes." }, { status: 429, headers: { "Retry-After": "900" } });
    if (!checkPassword(input.password, settings)) {
      state.studabLogin!.failures++;
      return NextResponse.json({ error: "That password did not match." }, { status: 401 });
    }
    state.studabLogin = { since: Date.now(), failures: 0 };
    const session = newSession(settings);
    response.cookies.set(sessionCookie, session.token, { httpOnly: true, secure: origin.startsWith("https:"), sameSite: "strict", path: "/", maxAge: session.age });
    return response;
  } catch { return NextResponse.json({ error: "Login is unavailable. Check local access settings." }, { status: 400 }); }
}
