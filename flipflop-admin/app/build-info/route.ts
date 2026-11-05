import { execFileSync } from "node:child_process";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function gitValue(args: string[]) {
  return execFileSync("git", args, {
    cwd: process.cwd(),
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
    timeout: 2000,
  }).trim();
}

export async function GET() {
  const source = {
    source_commit: process.env.NEXT_PUBLIC_SOURCE_COMMIT ?? "unknown",
    source_branch: process.env.NEXT_PUBLIC_SOURCE_BRANCH ?? "unknown",
    source_dirty: process.env.NEXT_PUBLIC_SOURCE_DIRTY === "true",
  };

  // In local DEV, read the checkout at request time so hot reloads and
  // autosyncs cannot leave the header displaying launch-time metadata.
  if (process.env.NODE_ENV === "development") {
    try {
      source.source_commit = gitValue(["rev-parse", "HEAD"]);
      source.source_branch = gitValue(["symbolic-ref", "--short", "-q", "HEAD"]) || "detached";
      source.source_dirty = Boolean(gitValue(["status", "--porcelain"]));
    } catch {
      // Use the build stamp if Git is temporarily unavailable.
    }
  }

  return NextResponse.json(source, { headers: { "Cache-Control": "no-store" } });
}
