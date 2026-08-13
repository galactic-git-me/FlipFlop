import { NextRequest, NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, verifyAdminToken } from "@/lib/admin-session";

// flipflop-admin has no auth of its own today — this is the single gate in
// front of every route. Keep the allowlist below tight; anything not listed
// requires a verified admin session.
const PUBLIC_PATHS = ["/login"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  const token = request.cookies.get(ADMIN_SESSION_COOKIE)?.value;
  const session = token ? await verifyAdminToken(token) : null;

  // /api/* is proxied (see next.config.ts rewrites) straight through to
  // flipflop-api, which now requires a Bearer admin token on its admin
  // routers (get_current_admin). The browser only ever holds the token in
  // this httpOnly cookie, so this is the one place that can attach it to the
  // outgoing request. Never redirect an API/XHR call to the /login HTML page
  // — an unauthenticated call should fall through and let the backend return
  // a proper 401 JSON response instead of corrupting a fetch() with HTML.
  if (pathname.startsWith("/api/")) {
    if (!session || !token) {
      return NextResponse.next();
    }
    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return NextResponse.next({ request: { headers } });
  }

  if (!session) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Run on every route except static assets and Next internals.
    "/((?!_next/static|_next/image|favicon.ico|api/session).*)",
  ],
};
