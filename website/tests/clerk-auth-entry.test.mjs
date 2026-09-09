import test from "node:test";
import assert from "node:assert/strict";
import { decideAuthEntry } from "../src/lib/abn-lead-gen/auth-entry.ts";

test("a revoked session with an unexpired JWT gets recovery, not a dashboard redirect loop", () => {
  assert.deepEqual(decideAuthEntry(true, { status: "signed-out" }), { kind: "recover" });
});
test("an anonymous browser gets the actual sign-in or sign-up form", () => {
  assert.deepEqual(decideAuthEntry(false, { status: "signed-out" }), { kind: "form" });
});
test("a freshly verified admin can enter the dashboard", () => {
  assert.deepEqual(decideAuthEntry(true, { status: "admin" }), { kind: "redirect", url: "/abn-lead-gen/dashboard" });
});
test("a verified ordinary account enters access pending without an admin redirect", () => {
  assert.deepEqual(decideAuthEntry(true, { status: "forbidden" }), { kind: "redirect", url: "/abn-lead-gen/access" });
});
test("provider verification failure renders a retry state with no auth widget or redirect", () => {
  for (const hasIdentity of [false, true]) assert.deepEqual(decideAuthEntry(hasIdentity, { status: "unavailable" }), { kind: "unavailable" });
});
