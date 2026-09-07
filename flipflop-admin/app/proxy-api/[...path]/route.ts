import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:4311").replace(/\/$/, "");

// Same-origin REST proxy. middleware attaches Authorization from the
// httpOnly admin_session cookie before this handler forwards to FastAPI.
async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = `${backendUrl}/api/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();

  for (const name of ["authorization", "content-type", "accept", "range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  // Do not rely solely on middleware: in some Next/Turbopack deployments the
  // request header override is not preserved when entering an App Router
  // handler. Read the session cookie here as the authoritative fallback.
  if (!headers.has("authorization")) {
    const cookieStore = await cookies();
    const token =
      cookieStore.get("admin_session")?.value ??
      cookieStore.get("admin_token")?.value;
    if (token) headers.set("authorization", `Bearer ${token}`);
  }

  const response = await fetch(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: "follow",
    signal: AbortSignal.timeout(120_000),
  });

  const responseHeaders = new Headers();
  for (const name of ["content-type", "content-disposition"]) {
    const value = response.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }

  return new NextResponse(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

export const GET = forward;
export const HEAD = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
