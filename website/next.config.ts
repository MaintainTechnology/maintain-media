import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  devIndicators: false,
  async headers() {
    return [{ source: "/abn-lead-gen/:path*", headers: [
      { key: "X-Maintain-Workspace", value: "abn-lead-gen" },
      { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
      { key: "Cache-Control", value: "private, no-store, max-age=0" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "no-referrer" },
    ] }];
  },
  // The brand-asset repo has its own lockfile one level up; pin the root here.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
