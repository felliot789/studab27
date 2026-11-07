import { NextRequest } from "next/server";
import { assertSafeKeys, object } from "./validation";

import { IMPORT_MAX_BYTES } from "./request-limits";
export { IMPORT_MAX_BYTES };

export async function jsonBody(request: NextRequest, limit = 1_500_000) {
  if (Number(request.headers.get("content-length") || 0) > limit) throw new Error("Request is too large.");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("A JSON request is required.");
  let total = 0;
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) { await reader.cancel(); throw new Error("Request is too large."); }
    chunks.push(value);
  }
  const parsed: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  assertSafeKeys(parsed);
  return object(parsed);
}
