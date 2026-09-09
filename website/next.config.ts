import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // The brand-asset repo has its own lockfile one level up; pin the root here.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
