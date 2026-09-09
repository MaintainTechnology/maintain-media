import { redirect } from "next/navigation";
import { getAdminSession } from "@/lib/abn-lead-gen/auth";
import { LeadGenDashboard } from "@/components/abn-lead-gen/dashboard";

export const dynamic = "force-dynamic";

export default async function LeadGenPage() {
  const admin = await getAdminSession();
  if (!admin) redirect("/abn-lead-gen/sign-in");
  return <LeadGenDashboard admin={admin} />;
}
