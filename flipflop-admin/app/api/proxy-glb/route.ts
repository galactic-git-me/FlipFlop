import { ADMIN_SESSION_COOKIE, verifyAdminToken } from "@/lib/admin-session";

const MAX_PROXY_MEDIA_BYTES = 100 * 1024 * 1024;
const MAX_REDIRECTS = 3;
const ALLOWED_MEDIA_HOSTS = new Set([
  "computerorbit.com",
  "www.computerorbit.com",
  "i.ebayimg.com",
  "vi.vipr.ebaydesc.com",
  "www.overclockers.co.uk",
  "www.scan.co.uk",
  "m.media-amazon.com",
  "images-eu.ssl-images-amazon.com",
  "images-na.ssl-images-amazon.com",
]);
const ALLOWED_MEDIA_TYPES = new Set([
  "model/gltf-binary", "application/octet-stream",
  "image/avif", "image/jpeg", "image/png", "image/webp",
  "video/mp4", "video/webm",
]);

function cookieValue(request: Request, name: string): string | null {
  const prefix = `${name}=`;
  return (request.headers.get("cookie") ?? "")
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length) ?? null;
}

export function isAllowedProxyMediaUrl(value: string): boolean {
  try {
    const url = new URL(value);
    if (url.username || url.password || url.search || url.hash) {
      return false;
    }

    const host = url.hostname.toLowerCase();
    const isProductionMedia =
      url.protocol === "https:" &&
      (host === "theflipflop.shop" || host === "www.theflipflop.shop") &&
      !url.port &&
      url.pathname.startsWith("/media/");
    const isLocalDevMedia =
      url.protocol === "http:" &&
      (host === "127.0.0.1" || host === "localhost" || host === "[::1]") &&
      url.port === "4311" &&
      url.pathname.startsWith("/api/3d-media/") &&
      url.pathname.toLowerCase().endsWith(".glb");
    const isApprovedExternalMedia =
      url.protocol === "https:" && !url.port && ALLOWED_MEDIA_HOSTS.has(host);

    return isProductionMedia || isLocalDevMedia || isApprovedExternalMedia;
  } catch {
    return false;
  }
}

function withGlbSizeLimit(body: ReadableStream<Uint8Array> | null): ReadableStream<Uint8Array> | null {
  if (!body) return null;
  let bytesSeen = 0;
  return body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      bytesSeen += chunk.byteLength;
      if (bytesSeen > MAX_PROXY_MEDIA_BYTES) {
        controller.error(new Error("Media exceeds the allowed size"));
        return;
      }
      controller.enqueue(chunk);
    },
  }));
}

export async function GET(request: Request) {
  const token = cookieValue(request, ADMIN_SESSION_COOKIE);
  if (!token || !(await verifyAdminToken(token))) {
    return new Response("Authentication required", { status: 401 });
  }

  const source = new URL(request.url).searchParams.get("url");
  if (!source || !isAllowedProxyMediaUrl(source)) {
    return new Response("Unsupported media source", { status: 400 });
  }

  try {
    let currentUrl = source;
    let upstream: Response | null = null;
    for (let redirectCount = 0; redirectCount <= MAX_REDIRECTS; redirectCount += 1) {
      upstream = await fetch(currentUrl, {
        redirect: "manual",
        signal: AbortSignal.timeout(120_000),
        headers: {
          Accept: "model/gltf-binary, application/octet-stream, image/avif, image/jpeg, image/png, image/webp, video/mp4, video/webm",
        },
      });

      if (![301, 302, 303, 307, 308].includes(upstream.status)) break;
      const location = upstream.headers.get("location");
      if (!location || redirectCount === MAX_REDIRECTS) {
        return new Response("GLB redirect rejected", { status: 502 });
      }
      currentUrl = new URL(location, currentUrl).toString();
      if (!isAllowedProxyMediaUrl(currentUrl)) {
        return new Response("Media redirect destination rejected", { status: 502 });
      }
    }

    if (!upstream?.ok) {
      return new Response("Failed to fetch media", { status: upstream?.status || 502 });
    }

    const contentType = (upstream.headers.get("content-type") || "")
      .split(";")[0]
      .trim()
      .toLowerCase();
    if (contentType && !ALLOWED_MEDIA_TYPES.has(contentType)) {
      return new Response("Unsupported media content type", { status: 415 });
    }
    const advertisedSize = Number(upstream.headers.get("content-length") || 0);
    if (advertisedSize > MAX_PROXY_MEDIA_BYTES) {
      return new Response("Media exceeds the allowed size", { status: 413 });
    }

    return new Response(withGlbSizeLimit(upstream.body), {
      headers: {
        "Content-Type": contentType || "application/octet-stream",
        ...(upstream.headers.get("content-length") ? { "Content-Length": upstream.headers.get("content-length")! } : {}),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return new Response("GLB fetch failed", { status: 502 });
  }
}
