import { assertAdminRequest } from "@/lib/abn-lead-gen/auth";
import { bridgeFailure, forwardLeadGen } from "@/lib/abn-lead-gen/bridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function handle(request: Request, context: { params: Promise<{ path: string[] }> }) {
  try {
    const admin = await assertAdminRequest(request, !["GET", "HEAD"].includes(request.method));
    const { path } = await context.params;
    return await forwardLeadGen(request, path, admin);
  } catch (error) { return bridgeFailure(error); }
}

export { handle as GET, handle as HEAD, handle as POST, handle as PATCH };
