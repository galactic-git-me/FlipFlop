import { NextRequest, NextResponse } from "next/server";

const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:4311").replace(/\/$/, "");

// Keep the REST client on the admin origin. This route receives the
// Authorization header added by middleware from the httpOnly admin_session
// cookie, then forwards the request to FastAPI server-to-server.
async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = `${backendUrl}/api/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();

  for (const name of ["authorization", "content-type", "accept", "range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const response = await fetch(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: "follow",
    signal: AbortSignal.timeout(120_000),
  });

  const responseHeaders = new Headers();
  const contentType = response.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);
  const contentDisposition = response.headers.get("content-disposition");
  if (contentDisposition) responseHeaders.set("content-disposition", contentDisposition);

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
