import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for the Docker multi-stage runner to work:
  // builds a self-contained server under .next/standalone/
  output: "standalone",
};

export default nextConfig;
