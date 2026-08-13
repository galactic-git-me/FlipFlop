"use client";

import { useState } from "react";
import { VENDOR_META } from "@/lib/vendors";

// No bundled/official vendor logo assets exist in this app -- fetches each
// vendor's real favicon from Google's public favicon service (no API key,
// no bundling of third-party brand assets into the repo) and falls back to
// a colour-coded monogram chip if that request ever fails.
export function VendorLogo({ vendor }: { vendor: string }) {
  const meta = VENDOR_META[vendor] ?? VENDOR_META.unknown;
  const [imgFailed, setImgFailed] = useState(false);

  if (imgFailed || !meta.domain) {
    return (
      <span
        className="flex items-center justify-center w-5 h-5 rounded text-[9px] font-bold text-white shrink-0"
        style={{ backgroundColor: meta.color }}
        title={meta.label}
      >
        {meta.mark}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- external favicon service
    <img
      src={`https://www.google.com/s2/favicons?domain=${meta.domain}&sz=32`}
      alt={meta.label}
      title={meta.label}
      width={20}
      height={20}
      className="w-5 h-5 rounded shrink-0 bg-white/90 p-0.5"
      onError={() => setImgFailed(true)}
    />
  );
}
