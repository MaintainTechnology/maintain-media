import type { Metadata } from "next";
import { UserButton } from "@clerk/nextjs";
import { redirect } from "next/navigation";
import { getAdminAccess } from "@/lib/abn-lead-gen/auth";
import { AuthShell } from "@/components/auth/auth-shell";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Workspace access", robots: { index: false, follow: false } };

export default async function WorkspaceAccessPage() {
  const access = await getAdminAccess();
  if (access.status === "signed-out") redirect("/sign-in");
  if (access.status === "admin") redirect("/abn-lead-gen/dashboard");
  const unavailable = access.status === "unavailable";
  return <AuthShell
    eyebrow="ABN Lead Gen"
    title={unavailable ? "We couldn’t check your access." : "Your account is ready."}
    description={unavailable
      ? "Account verification is temporarily unavailable. Try again in a moment."
      : "The lead workspace is for Maintain Media admins. Ask the person managing Maintain Media to give your account admin access."}
    note="Creating an account does not automatically grant access to business leads, reports or engine settings."
  >
    <div className="flex flex-wrap items-center gap-4">
      <a href="/abn-lead-gen/dashboard" className="btn btn-primary">Check workspace access</a>
      <div className="flex items-center gap-3 text-sm text-ink-2"><UserButton /><span>Your account</span></div>
    </div>
  </AuthShell>;
}
