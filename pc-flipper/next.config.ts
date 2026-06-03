import type { NextConfig } from "next";

const publicHost = process.env.PUBLIC_HOST?.trim();
const allowedOrigins = [
  "localhost",
  "127.0.0.1",
  "andromeda-ts",
  "andromeda-ts.tail0862d0.ts.net",
  ...(publicHost ? [publicHost] : []),
];

// In Docker the backend is reachable at http://backend:8000.
// In local dev it falls back to localhost:4311.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:4311";

const nextConfig: NextConfig = {
  transpilePackages: ["three", "postprocessing"],
  allowedDevOrigins: allowedOrigins,
  // Prevent Next.js stripping trailing slashes before proxying — FastAPI
  // redirects paths without them and the Location header would point to the
  // internal backend hostname the browser can't reach.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
