/** A larger rendition of the same image ID; never a different product photo. */
export function originalImageUrl(value: string): string {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) return value;
    if (["m.media-amazon.com", "images-na.ssl-images-amazon.com", "images-eu.ssl-images-amazon.com"].includes(url.hostname)) {
      url.pathname = url.pathname.replace(/(\/images\/I\/[^/]+?)\._[^/]+_\.(jpe?g|png|webp)$/i, "$1.$2");
    } else if (url.hostname === "i.ebayimg.com") {
      url.pathname = url.pathname.replace(/\/s-l(\d+)\.(jpe?g|png|webp)$/i, (_, size: string, ext: string) => `/s-l${Math.max(1600, Number(size))}.${ext}`);
    } else return value;
    return url.href;
  } catch { return value; }
}
