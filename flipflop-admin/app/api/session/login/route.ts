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

  const backendResponse = await fetch(`${backendUrl}/api/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
  });

  if (!backendResponse.ok) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const { access_token } = await backendResponse.json();

  const response = NextResponse.json({ ok: true });
  const maxAge = 60 * 60 * 12; // matches the 12h expiry set in admin_auth_service.py
  const secure = process.env.NODE_ENV === "production";

  // Two cookies, same token: `admin_session` (httpOnly) is what middleware.ts
  // trusts for page-gating and for injecting the Authorization header on
  // proxied /api/* rewrites. `admin_token` (readable by client JS) exists only
  // because lib/api.ts calls the backend directly at an absolute origin
  // (NEXT_PUBLIC_API_URL) for some endpoints, which never passes through
  // middleware — those calls need the token themselves to set the header.
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
