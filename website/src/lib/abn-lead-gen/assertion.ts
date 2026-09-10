import { createHash, createHmac, randomUUID } from "node:crypto";

/** Only the current Clerk server authority may construct this input. */
export function staffAssertion(key: string, actor: { actorId?: string; scopes?: string[] }, method: string,
  path: string, body: string, requestId: string, idempotencyKey = "", now = Math.floor(Date.now() / 1000)): string {
  const scopes = new Set(["admin", "operator", "reviewer", "owner", "compliance"]);
  if (!/^[A-Za-z0-9_-]{43,256}$/.test(key) || !/^user_[A-Za-z0-9]{1,200}$/.test(actor.actorId ?? "")
    || !actor.scopes?.length || actor.scopes.some(scope => !scopes.has(scope))) throw new Error("ENGINE_ACTOR_INVALID");
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const unsigned = `${encode({ alg: "HS256", typ: "JWT" })}.${encode({
    iss: "maintain-media-website", aud: "abr-engine-live", sub: actor.actorId, scopes: actor.scopes,
    iat: now, exp: now + 60, jti: randomUUID(), method, path, request_id: requestId,
    idempotency_key: idempotencyKey, body_sha256: createHash("sha256").update(body).digest("hex"),
  })}`;
  return `${unsigned}.${createHmac("sha256", key).update(unsigned).digest("base64url")}`;
}
