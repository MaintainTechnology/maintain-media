export type AuthEntryDecision =
  | { kind: "form" | "recover" | "unavailable" }
  | { kind: "redirect"; url: "/abn-lead-gen/dashboard" | "/abn-lead-gen/access" };

/** A JWT can remain valid briefly after Clerk revokes the underlying session. */
export function decideAuthEntry(hasIdentity: boolean, access: { status: "admin" | "forbidden" | "signed-out" | "unavailable" }): AuthEntryDecision {
  if (access.status === "unavailable") return { kind: "unavailable" };
  if (access.status === "admin") return { kind: "redirect", url: "/abn-lead-gen/dashboard" };
  if (access.status === "forbidden") return { kind: "redirect", url: "/abn-lead-gen/access" };
  return { kind: hasIdentity ? "recover" : "form" };
}
