import DOMPurify from "isomorphic-dompurify";

const LISTING_TAGS = [
  "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li",
  "blockquote", "strong", "b", "em", "i", "u", "a", "br", "hr",
  "span", "div", "table", "tr", "td", "th", "tbody", "thead",
];

export function sanitizeListingHtml(value: string): string {
  return DOMPurify.sanitize(value, {
    ALLOWED_TAGS: LISTING_TAGS,
    ALLOWED_ATTR: ["style", "href", "target", "rel", "class"],
  });
}
