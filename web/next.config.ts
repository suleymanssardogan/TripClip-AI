import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{
      source: "/api/web/:path*",
      destination: `${process.env.WEB_BFF_URL || "http://127.0.0.1:8002"}/api/web/:path*`,
    }];
  },
};

export default nextConfig;
