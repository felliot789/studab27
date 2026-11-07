import "server-only";
import { readFile } from "node:fs/promises";
import { createHmac, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

export type Access = { enabled: boolean; origins: string[]; passwordSalt?: string; passwordHash?: string; sessionSecret?: string; sessionDays?: number; lan?: { origin: string; proxySecret: string; passwordSalt: string; passwordHash: string; sessionSecret: string } };
export const sessionCookie = "studab27-session";
export async function accessSettings(): Promise<Access> {
  // The launch script supplies a runtime path, keeping the secret file out of
  // Next's static dependency trace (including its separate Proxy trace).
  const filename = process.env.STUDAB27_CONFIG_PATH;
  if (!filename) throw new Error("Start StudAb27 with npm run dev or npm start.");
  try {
    const config = JSON.parse(await readFile(filename, "utf8"));
    const access = config.access as Access;
    if (!access || !Array.isArray(access.origins)) throw new Error("Invalid access settings");
    for (const origin of access.origins) {
      const url = new URL(origin);
      const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
      if (url.origin !== origin || url.username || url.password || (url.protocol !== "https:" && !(loopback && url.protocol === "http:"))) throw new Error("Only exact HTTPS remote origins and loopback HTTP origins are allowed");
    }
    if (access.enabled !== true || !access.sessionSecret || !access.passwordHash || !access.passwordSalt) throw new Error("Login protection must be configured before using Schola settings");
    if (access.lan) {
      const lan = access.lan, url = new URL(lan.origin);
      if (url.origin !== lan.origin || url.protocol !== "http:" || !/^192\.168\.\d{1,3}\.\d{1,3}$/.test(url.hostname) || !lan.proxySecret || !lan.passwordSalt || !lan.passwordHash || !lan.sessionSecret) throw new Error("Invalid LAN access settings");
    }
    return access;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return { enabled: false, origins: [] };
    throw new Error("Workspace access settings need local attention.");
  }
}
export function trustedOrigin(host: string, settings: Access) {
  if (!settings.enabled) return /^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/.test(host) ? `http://${host}` : null;
  return settings.origins.find(origin => { try { return new URL(origin).host === host; } catch { return false; } }) || null;
}
function equal(a: string, b: string) {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}
export function requestAccess(settings: Access, host: string, proxySecret: string | null): Access {
  const lan = settings.lan;
  if (lan && new URL(lan.origin).host === host && proxySecret && equal(proxySecret, lan.proxySecret)) {
    return { ...settings, ...lan, origins: [lan.origin], lan: undefined };
  }
  return settings;
}
function signature(payload: string, settings: Access) { return createHmac("sha256", settings.sessionSecret!).update(payload).digest("base64url"); }
export function validSession(token: string | undefined, settings: Access) {
  if (!settings.enabled) return true;
  if (!token || token.length > 300) return false;
  const [expires, nonce, sig, extra] = token.split(".");
  const end = Number(expires);
  return !extra && !!nonce && !!sig && Number.isSafeInteger(end) && end > Date.now() && end <= Date.now() + 31 * 86400000 && equal(signature(`${expires}.${nonce}`, settings), sig);
}
export function newSession(settings: Access) {
  const age = Math.min(30, Math.max(1, settings.sessionDays || 14)) * 86400;
  const payload = `${Date.now() + age * 1000}.${randomBytes(24).toString("base64url")}`;
  return { token: `${payload}.${signature(payload, settings)}`, age };
}
export function checkPassword(password: unknown, settings: Access) {
  if (typeof password !== "string" || !password || password.length > 500 || !settings.passwordSalt || !settings.passwordHash) return false;
  const hash = scryptSync(password, Buffer.from(settings.passwordSalt, "hex"), 64, { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 }).toString("hex");
  return equal(hash, settings.passwordHash);
}
// Enforced again where private data is read, independently of Proxy routing.
export async function requireAccess() {
  const h = await headers();
  const settings = requestAccess(await accessSettings(), (h.get("host") || "").toLowerCase(), h.get("x-studab-lan-proxy"));
  if (!trustedOrigin((h.get("host") || "").toLowerCase(), settings)) throw new Error("Untrusted workspace host.");
  if (!validSession((await cookies()).get(sessionCookie)?.value, settings)) redirect("/login");
}
