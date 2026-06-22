import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://andromeda-ts:4311";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["andromeda-ts"],
  async rewrites() {
    return [
      {
        source: "/api/orders/:path*",
        destination: `${backendUrl}/api/orders/:path*`,
      },
      {
        source: "/api/stripe/:path*",
        destination: `${backendUrl}/api/stripe/:path*`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${backendUrl}/api/admin/:path*`,
      },
    ];
  },
};

export default nextConfig;
