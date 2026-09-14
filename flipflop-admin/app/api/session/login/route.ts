import { NextRequest, NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:4311";

/** Proxies to the real backend login (flipflop-api /api/admin/auth/login) and, on
 * success, stores the returned JWT as an httpOnly cookie on this app's own origin —
 * a browser can't set httpOnly cookies itself, so this route does it server-side. */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${backendUrl}/api/admin/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
    });
  } catch (error) {
    console.error("Admin login backend request failed", error);
    return NextResponse.json(
      { error: "Could not reach the login server. Please try again or check that the backend is running." },
      { status: 503 },
    );
  }

  if (!backendResponse.ok) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const { access_token } = await backendResponse.json();

  const response = NextResponse.json({ ok: true });
  const maxAge = 60 * 60 * 12; // matches the 12h expiry set in admin_auth_service.py
  // The admin is often opened from a phone over the local network using
  // http://<computer-ip>:4312, even when Next is running in production mode.
  // A Secure cookie is silently rejected in that case, which looks like a
  // successful submit followed by an immediate reload of /login. Follow the
  // actual request protocol instead of NODE_ENV.
  const secure = request.nextUrl.protocol === "https:";

  // Two cookies, same token: `admin_session` (httpOnly) is what proxy.ts
  // trusts for page-gating and for injecting the Authorization header on
  // proxied /api/* rewrites. `admin_token` (readable by client JS) exists only
  // because lib/api.ts calls the backend directly at an absolute origin
  // (NEXT_PUBLIC_API_URL) for some endpoints, which never passes through
  // proxy — those calls need the token themselves to set the header.
  response.cookies.set(ADMIN_SESSION_COOKIE, access_token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge,
  });
  response.cookies.set("admin_token", access_token, {
    httpOnly: false,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge,
  });
  return response;
}
