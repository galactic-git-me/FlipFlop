import type { NextConfig } from "next";
import path from "path";

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
const gemradarUrl = process.env.GEMRADAR_URL ?? "http://localhost:18000";
const ebayOpsBackendUrl = (process.env.EBAY_OPS_BACKEND_URL ?? backendUrl).replace(/\/$/, "");

const nextConfig: NextConfig = {
  turbopack: {
    root: path.join(__dirname),
  },
  // GLB uploads are proxied through the Next.js route handler before they
  // reach FastAPI. Keep this in sync with the backend's 100 MB model limit.
  experimental: {
    proxyClientMaxBodySize: "100mb",
  },
  transpilePackages: ["three", "postprocessing"],
  allowedDevOrigins: allowedOrigins,
  // Prevent Next.js stripping trailing slashes before proxying — FastAPI
  // redirects paths without them and the Location header would point to the
  // internal backend hostname the browser can't reach.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      // Gem Radar API (separate service on port 18000)
      {
        source: "/api/gem-radar/:path*",
        destination: `${gemradarUrl}/api/gem-radar/:path*`,
      },
      // Main backend (port 4311 by default)
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      // eBay OAuth state is owned by the deployed operations API, even when
      // the admin UI is running locally. Keep these ahead of the catch-all
      // proxy rewrite below.
      {
        source: "/proxy-api/ebay/oauth/:path*",
        destination: `${ebayOpsBackendUrl}/api/ebay/oauth/:path*`,
      },
      {
        source: "/proxy-api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/uploads/:path*",
        destination: `${backendUrl}/uploads/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
