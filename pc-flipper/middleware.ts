import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Ensure /api/* requests always reach the FastAPI backend with a trailing slash.
 * Next.js strips trailing slashes from paths before applying rewrites, which causes
 * FastAPI to return a 307 redirect to http://backend:8000/... — an internal URL the
 * browser can't resolve.  Normalising the slash here (before rewrites run) prevents
 * that redirect entirely.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith("/api/") && !pathname.endsWith("/")) {
    const url = request.nextUrl.clone();
    url.pathname = pathname + "/";
    return NextResponse.rewrite(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};
