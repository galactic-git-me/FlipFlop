const ALLOWED_IMAGE_HOSTS = new Set([
  "computerorbit.com",
  "www.computerorbit.com",
  "i.ebayimg.com",
  "www.overclockers.co.uk",
  "www.scan.co.uk",
  "m.media-amazon.com",
  "images-eu.ssl-images-amazon.com",
  "images-na.ssl-images-amazon.com",
]);
const MAX_IMAGE_BYTES = 12 * 1024 * 1024;

function isAllowedImageUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ALLOWED_IMAGE_HOSTS.has(url.hostname);
  } catch {
    return false;
  }
}

export async function GET(request: Request) {
  const source = new URL(request.url).searchParams.get("url");
  if (!source || !isAllowedImageUrl(source)) {
    return new Response("Unsupported image host", { status: 400 });
  }

  let currentUrl = source;
  try {
    let upstream: Response | null = null;
    for (let redirectCount = 0; redirectCount <= 3; redirectCount += 1) {
      upstream = await fetch(currentUrl, {
        redirect: "manual",
        signal: AbortSignal.timeout(15_000),
        headers: {
          Accept: "image/avif,image/webp,image/png,image/jpeg",
          "User-Agent": "Mozilla/5.0",
        },
      });

      if (![301, 302, 303, 307, 308].includes(upstream.status)) break;
      const location = upstream.headers.get("location");
      if (!location || redirectCount === 3) return new Response("Image redirect rejected", { status: 502 });
      currentUrl = new URL(location, currentUrl).toString();
      if (!isAllowedImageUrl(currentUrl)) return new Response("Image redirect host rejected", { status: 502 });
    }

    if (!upstream?.ok) return new Response("Image fetch failed", { status: upstream?.status || 502 });
    const contentType = (upstream.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!["image/jpeg", "image/png", "image/webp", "image/avif"].includes(contentType)) {
      return new Response("Unsupported image type", { status: 415 });
    }

    const advertisedSize = Number(upstream.headers.get("content-length") || 0);
    if (advertisedSize > MAX_IMAGE_BYTES) return new Response("Image is too large", { status: 413 });
    const bytes = await upstream.arrayBuffer();
    if (bytes.byteLength > MAX_IMAGE_BYTES) return new Response("Image is too large", { status: 413 });
    return new Response(bytes, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return new Response("Image fetch failed", { status: 502 });
  }
}
