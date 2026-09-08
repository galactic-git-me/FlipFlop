import { NextRequest, NextResponse } from "next/server";

const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:4311").replace(/\/$/, "");
const ebayOpsBackendUrl = (process.env.EBAY_OPS_BACKEND_URL ?? "").replace(/\/$/, "");

function backendForPath(path: string[]): string {
  if (!ebayOpsBackendUrl) return backendUrl;
  const value = path.join("/");
  // Keep local catalogue/build editing local. Only seller-authorized eBay
  // operations use the deployed API, which owns the connected eBay token.
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

// Same-origin REST proxy. middleware attaches Authorization from the
// httpOnly admin_session cookie before this handler forwards to FastAPI.
async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = `${backendForPath(path)}/api/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();

  for (const name of ["authorization", "content-type", "accept", "range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  // Do not rely solely on middleware: in some Next/Turbopack deployments the
  // request header override is not preserved when entering an App Router
  // handler. Read the session cookie here as the authoritative fallback.
  if (!headers.has("authorization")) {
    const cookieHeader = request.headers.get("cookie") ?? "";
    const cookieValue = (name: string) => cookieHeader
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${name}=`))
      ?.slice(name.length + 1);
    const token = cookieValue("admin_session") ?? cookieValue("admin_token");
    if (token) headers.set("authorization", `Bearer ${token}`);
  }

  const fetchOptions = {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: "manual" as const,
    signal: AbortSignal.timeout(120_000),
  };
  let response = await fetch(target, fetchOptions);

  // Preserve Authorization across backend canonical-host/trailing-slash
  // redirects. Native fetch can drop it when following to another origin.
  for (let hop = 0; hop < 3 && response.status >= 300 && response.status < 400; hop += 1) {
    const location = response.headers.get("location");
    if (!location) break;
    response = await fetch(new URL(location, target), fetchOptions);
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
