import { describe, expect, it } from "vitest";
import { sanitizeListingHtml } from "../../lib/sanitize-listing-html.ts";

describe("sanitizeListingHtml", () => {
  it("preserves allowed listing markup and strips executable content", () => {
    const result = sanitizeListingHtml(
      '<p onclick="alert(1)">Build <strong>details</strong></p><img src=x onerror="alert(2)"><script>alert(3)</script><a href="javascript:alert(4)">link</a>',
    );

    expect(result).toContain("<p>Build <strong>details</strong></p>");
    expect(result).not.toMatch(/onclick|onerror|<script|javascript:/i);
  });
});
