import type { NextConfig } from "next";

const publicHost = process.env.PUBLIC_HOST?.trim();
const allowedOrigins = [
  "localhost",
  "127.0.0.1",
  "andromeda-ts",
  "andromeda-ts.tail0862d0.ts.net",
  ...(publicHost ? [publicHost] : []),
];

const nextConfig: NextConfig = {
  transpilePackages: ["three", "postprocessing"],
  allowedDevOrigins: allowedOrigins,
};

export default nextConfig;
