import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://andromeda-ts:4311";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["andromeda-ts"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
