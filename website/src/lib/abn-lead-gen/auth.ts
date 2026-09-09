import "server-only";
import { cookies } from "next/headers";
import {
  ADMIN_COOKIE, AuthError, authorizeAdminRequest, readAdminConfiguration, verifyAdminToken,
  type AdminSession,
} from "./auth-core";

export { AuthError } from "./auth-core";
export type { AdminSession } from "./auth-core";

export async function adminAccessConfigured(): Promise<boolean> {
  try {
    const config = await readAdminConfiguration();
    return config.accounts.some((account) => account.enabled && account.role === "admin");
  } catch {
    return false;
  }
}

export async function getAdminSession(): Promise<AdminSession | null> {
  const matches = (await cookies()).getAll(ADMIN_COOKIE);
  if (matches.length !== 1) return null;
  try {
    return verifyAdminToken(matches[0].value, await readAdminConfiguration());
  } catch (error) {
    if (error instanceof AuthError) return null;
    throw error;
  }
}

export async function assertAdminRequest(request: Request, mutation = false): Promise<AdminSession> {
  return authorizeAdminRequest(request, await readAdminConfiguration(), mutation);
}
