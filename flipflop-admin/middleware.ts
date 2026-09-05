import { NextRequest, NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, verifyAdminToken } from "@/lib/admin-session";

// Page routes stay ungated for development, but /api/* is proxied (see
// next.config.ts rewrites) straight through to flipflop-api, which requires
// a Bearer admin token on its admin routers (get_current_admin). The browser
// only ever holds the token in this httpOnly cookie, so this is the one place
// that can attach it to the outgoing request.
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/api/")) {
    const token = request.cookies.get(ADMIN_SESSION_COOKIE)?.value;
    const session = token ? await verifyAdminToken(token) : null;
    if (!session || !token) {
      return NextResponse.next();
    }
    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return NextResponse.next({ request: { headers } });
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Run on every route except static assets (anything under public/, by
    // extension) and Next internals. Without the extension exclusion, image
    // requests like /pics/logo.png get caught by the "no session" branch
    // below and redirected to an HTML /login page instead of the image.
    "/((?!_next/static|_next/image|favicon.ico|api/session|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|mp4|webm|woff2?|ttf|glb)$).*)",
  ],
};
