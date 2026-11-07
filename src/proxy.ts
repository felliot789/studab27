import { NextRequest, NextResponse } from "next/server";
import { accessSettings, requestAccess, sessionCookie, trustedOrigin, validSession } from "./lib/access";

export async function proxy(request: NextRequest) {
  let settings;
  try { settings = await accessSettings(); }
  catch { return new NextResponse("Workspace access needs local attention.", { status: 503 }); }
  const host = (request.headers.get("host") || "").toLowerCase();
  settings = requestAccess(settings, host, request.headers.get("x-studab-lan-proxy"));
  const origin = trustedOrigin(host, settings);
  if (!origin) return new NextResponse("Untrusted workspace host.", { status: 403 });
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
    if (request.headers.get("origin") !== origin) return new NextResponse("Same-origin requests are required.", { status: 403 });
  }
  if (!["/login", "/api/session"].includes(request.nextUrl.pathname) && !validSession(request.cookies.get(sessionCookie)?.value, settings)) {
    if (request.nextUrl.pathname.startsWith("/api/")) return NextResponse.json({ error: "Sign in to your workspace." }, { status: 401 });
    return NextResponse.redirect(new URL("/login", origin));
  }
  return NextResponse.next();
}

export const config = { matcher: "/((?!_next/static|_next/image|favicon.ico).*)" };
