import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { getAdminAccess } from "@/lib/abn-lead-gen/auth";
import { decideAuthEntry, type AuthEntryDecision } from "@/lib/abn-lead-gen/auth-entry";
import { AuthForm } from "./auth-form";
import { AuthShell } from "./auth-shell";
import { SessionRecovery } from "./session-recovery";

export async function AuthEntry({ mode }: { mode: "sign-in" | "sign-up" }) {
  let decision: AuthEntryDecision;
  try {
    const identity = await auth();
    // Check active Clerk session and current admin authority before redirecting a JWT holder.
    const access = identity.userId ? await getAdminAccess() : { status: "signed-out" as const };
    decision = decideAuthEntry(!!identity.userId, access);
  } catch {
    decision = { kind: "unavailable" };
  }
  if (decision.kind === "redirect") redirect(decision.url);
  if (decision.kind === "recover") return <AuthShell eyebrow="Maintain Media account" title="Let’s refresh your sign-in." description="Your previous account session is no longer active. Reset it here to sign in again.">
    <SessionRecovery />
  </AuthShell>;
  if (decision.kind === "unavailable") return <AuthShell eyebrow="Maintain Media account" title="We couldn’t check your account." description="Account verification is temporarily unavailable. Try again in a moment to continue securely.">
    <a href={`/${mode}`} className="btn btn-primary">Try again</a>
  </AuthShell>;
  return mode === "sign-in"
    ? <AuthShell eyebrow="Sign in · Maintain Media" title="Welcome back." description="Sign in to your Maintain Media account. Your lead workspace is ready when you are." note="ABN Lead Gen is available to approved Maintain Media administrators. Your account keeps your profile and sign-in details together."><AuthForm mode={mode} /></AuthShell>
    : <AuthShell eyebrow="Sign up · Maintain Media" title="Make yourself at home." description="Create your Maintain Media account to get started. You can manage your profile and sign-in security from your account menu." note="Creating an account does not grant admin access. A Maintain Media administrator must approve access before you can open ABN Lead Gen."><AuthForm mode={mode} /></AuthShell>;
}
