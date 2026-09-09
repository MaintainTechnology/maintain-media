import "server-only";
import { auth, clerkClient } from "@clerk/nextjs/server";
import { resolveClerkAdminAccess, requireAdminAccess, authorizeClerkRequest } from "./clerk-access-service";
import type { AdminSession } from "./auth-core";

export { AuthError } from "./auth-core";
export type { AdminSession } from "./auth-core";
export type { AdminAccess } from "./clerk-access-service";

/** Resolve Clerk afresh for each page/data/action/report request; never cache privileges across requests. */
export async function getAdminAccess() {
  return resolveClerkAdminAccess({
    authenticate: async () => {
      const identity = await auth();
      return { userId: identity.userId, sessionId: identity.sessionId };
    },
    getSession: async (id) => (await clerkClient()).sessions.getSession(id),
    getUser: async (id) => (await clerkClient()).users.getUser(id),
    // The SDK/framework loads configuration; keys never leave this server-only module.
    secret: process.env.CLERK_SECRET_KEY,
  });
}

export async function getAdminSession(): Promise<AdminSession | null> {
  const access = await getAdminAccess();
  if (access.status === "signed-out" || access.status === "forbidden") return null;
  return requireAdminAccess(access);
}

export async function assertAdminRequest(request: Request, mutation = false): Promise<AdminSession> {
  return authorizeClerkRequest(request, await getAdminAccess(), mutation);
}
