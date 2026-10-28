import {expect,it} from "vitest";
import {originalImageUrl} from "./model-reference-images";
it("uses the original rendition without changing the selected Amazon photo identity",()=>{
  expect(originalImageUrl("https://m.media-amazon.com/images/I/41RmXmwB43L._AC_US40_.jpg")).toBe("https://m.media-amazon.com/images/I/41RmXmwB43L.jpg");
});
it("keeps unrelated or spoofed image hosts unchanged",()=>{
  const url="https://m.media-amazon.com.attacker.invalid/images/I/photo._AC_US40_.jpg";
  expect(originalImageUrl(url)).toBe(url);
});
it("upgrades eBay thumbnails without reducing an already larger rendition",()=>{
  expect(originalImageUrl("https://i.ebayimg.com/images/g/key/s-l64.jpg")).toContain("s-l1600.jpg");
  expect(originalImageUrl("https://i.ebayimg.com/images/g/key/s-l2000.jpg")).toContain("s-l2000.jpg");
});
