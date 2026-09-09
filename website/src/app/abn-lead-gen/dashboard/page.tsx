import { redirect } from "next/navigation";
import { getAdminAccess } from "@/lib/abn-lead-gen/auth";
import { LeadGenDashboard } from "@/components/abn-lead-gen/dashboard";
import { AuthShell } from "@/components/auth/auth-shell";

export const dynamic = "force-dynamic";

export default async function LeadGenPage() {
  const access = await getAdminAccess();
  if (access.status === "signed-out") redirect("/sign-in");
  if (access.status === "forbidden") redirect("/abn-lead-gen/access");
  if (access.status === "unavailable") {
    return <AuthShell eyebrow="ABN Lead Gen" title="We couldn’t check your access." description="Account verification is temporarily unavailable. Your lead workspace stays locked until we can verify your admin access.">
      <a href="/abn-lead-gen/dashboard" className="btn btn-primary">Try again</a>
    </AuthShell>;
  }
  return <LeadGenDashboard admin={access.admin} />;
}
