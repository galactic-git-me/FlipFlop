import { NextRequest, NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, verifyAdminToken } from "@/lib/admin-session";

function clearLegacyAdminCookie(response: NextResponse): NextResponse {
  response.cookies.delete("admin_token");
  return response;
}

// Page routes stay ungated for development, but /api/* is proxied (see
// next.config.ts rewrites) straight through to flipflop-api, which requires
// a Bearer admin token on its admin routers (get_current_admin). The browser
// only ever holds the token in this httpOnly cookie, so this is the one place
// that can attach it to the outgoing request.
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // This switch exists only for local Playwright runs. Never let a deployment
  // environment setting disable the admin session checks.
  const playwrightTestMode =
    process.env.PLAYWRIGHT_TEST === "1" && process.env.NODE_ENV !== "production";
  const token = request.cookies.get(ADMIN_SESSION_COOKIE)?.value;
  const session = token ? await verifyAdminToken(token) : null;

  if (pathname.startsWith("/api/") || pathname.startsWith("/proxy-api/")) {
    const stateChanging = ["POST", "PUT", "PATCH", "DELETE"].includes(request.method);
    if (
      stateChanging &&
      !playwrightTestMode &&
      request.headers.get("origin") !== request.nextUrl.origin
    ) {
      return clearLegacyAdminCookie(NextResponse.json(
        { detail: "Cross-origin request rejected" },
        { status: 403 },
      ));
    }

    if (!session || !token) {
      if (playwrightTestMode) return clearLegacyAdminCookie(NextResponse.next());
      return clearLegacyAdminCookie(NextResponse.json(
        { detail: "Authentication required" },
        { status: 401 },
      ));
    }
    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return clearLegacyAdminCookie(NextResponse.next({ request: { headers } }));
  }

  // Do not render dashboard pages without the session required by their API
  // calls. Previously these pages loaded first and produced a cascade of
  // "Missing authorization header" errors from their useEffect hooks.
  if (pathname !== "/login" && !playwrightTestMode && (!session || !token)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("reason", token ? "session_invalid" : "session_missing");
    return clearLegacyAdminCookie(NextResponse.redirect(loginUrl));
  }

  return clearLegacyAdminCookie(NextResponse.next());
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
