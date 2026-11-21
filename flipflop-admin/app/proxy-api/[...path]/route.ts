import { NextRequest, NextResponse } from "next/server";

const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:4311").replace(/\/$/, "");
const ebayOpsBackendUrl = (process.env.EBAY_OPS_BACKEND_URL ?? "").replace(/\/$/, "");

function backendForPath(path: string[]): string {
  if (!ebayOpsBackendUrl) return backendUrl;
  const value = path.join("/");
  // Keep all local development operations on the configured local backend.
  // A deployed operations backend is an explicit deployment override only.
  if (
    value === "ebay/oauth/authorize-url" ||
    value === "ebay/oauth/status" ||
    value === "ebay/oauth/disconnect" ||
    value === "manual-builds/ebay-fulfillment-policies" ||
    /^manual-builds\/[^/]+\/(post-to-ebay|publish-ebay-draft|ebay-listing|sync-ebay-order)$/.test(value)
  ) {
    return ebayOpsBackendUrl;
  }
  return backendUrl;
}

// Same-origin REST proxy. Authorization comes only from the verified
// httpOnly admin_session cookie.
async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const pathValue = path.join("/");
  const target = `${backendForPath(path)}/api/${pathValue}${request.nextUrl.search}`;
  const backendOrigin = new URL(target).origin;
  // The Gem build route waits for a local compatibility review that can take
  // up to 120 seconds. Keep the longer deadline scoped to this one endpoint.
  const upstreamTimeout = pathValue === "gem-radar/gem-build-concepts" ? 180_000 : 120_000;
  const headers = new Headers();

  for (const name of ["authorization", "content-type", "accept", "range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  // Do not rely solely on proxy: in some Next/Turbopack deployments the
  // request header override is not preserved when entering an App Router
  // handler. Read the session cookie here as the authoritative fallback.
  if (!headers.has("authorization")) {
    const cookieHeader = request.headers.get("cookie") ?? "";
    const cookieValue = (name: string) => cookieHeader
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${name}=`))
      ?.slice(name.length + 1);
    const token = cookieValue("admin_session");
    if (token) headers.set("authorization", `Bearer ${token}`);
  }

  const fetchOptions = {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: "manual" as const,
    signal: AbortSignal.timeout(upstreamTimeout),
  };
  // The public production endpoint sits behind Caddy and can occasionally
  // reset an idle HTTP connection. Retry once so a transient reset does not
  // surface to the browser as the opaque `TypeError: Failed to fetch`.
  let response: Response;
  let currentTarget = target;
  try {
    response = await fetch(currentTarget, fetchOptions);
  } catch (error) {
    try {
      response = await fetch(currentTarget, fetchOptions);
    } catch (retryError) {
      console.error(`[proxy-api] upstream unavailable for ${request.method} /api/${pathValue}`, retryError ?? error);
      return NextResponse.json(
        { detail: "Backend API is unavailable" },
        { status: 502 },
      );
    }
  }

  // Preserve Authorization across backend canonical-host/trailing-slash
  // redirects. Native fetch can drop it when following to another origin.
  for (let hop = 0; hop < 3 && response.status >= 300 && response.status < 400; hop += 1) {
    const location = response.headers.get("location");
    if (!location) break;
    let redirectTarget: URL;
    try {
      redirectTarget = new URL(location, currentTarget);
    } catch {
      return NextResponse.json({ detail: "Backend redirect rejected" }, { status: 502 });
    }
    if (
      redirectTarget.origin !== backendOrigin ||
      !redirectTarget.pathname.startsWith("/api/") ||
      redirectTarget.username ||
      redirectTarget.password
    ) {
      return NextResponse.json({ detail: "Backend redirect rejected" }, { status: 502 });
    }
    currentTarget = redirectTarget.toString();
    response = await fetch(currentTarget, fetchOptions);
  }

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
