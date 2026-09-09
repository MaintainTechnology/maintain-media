import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  devIndicators: false,
  // Preserve 127.0.0.1 in Clerk's internal rewrite; Next's localhost normalization
  // otherwise proxies the request back into itself (vercel/next.js#94745).
  skipProxyUrlNormalize: true,
  async headers() {
    return [
      { source: "/abn-lead-gen/:path*", workspace: "abn-lead-gen" },
      { source: "/sign-in/:path*", workspace: "maintain-media-auth" },
      { source: "/sign-up/:path*", workspace: "maintain-media-auth" },
    ].map(({ source, workspace }) => ({ source, headers: [
      { key: "X-Maintain-Workspace", value: workspace },
      { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
      { key: "Cache-Control", value: "private, no-store, max-age=0" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "no-referrer" },
    ] }));
  },
  // The brand-asset repo has its own lockfile one level up; pin the root here.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
