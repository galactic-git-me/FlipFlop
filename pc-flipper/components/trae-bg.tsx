"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { ErrorBoundary } from "./error-boundary";

// Start downloading the JS module immediately, in parallel with the image fetch
const modulePromise = import("./GridDistortion");
const GridDistortion = dynamic(() => modulePromise, { ssr: false });

export function TraeBg() {
  const [imageSrc, setImageSrc] = useState<string>("/space-bg.jpg");

  useEffect(() => {
    let blobUrl: string | null = null;
    let cancelled = false;

    fetch("/api/nasa-bg")
      .then((r) => {
        if (!r.ok) throw new Error(`NASA bg route failed: ${r.status}`);
        const ct = r.headers.get("content-type") ?? "";
        if (!ct.startsWith("image/")) throw new Error(`Unexpected content-type: ${ct}`);
        return r.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        blobUrl = URL.createObjectURL(blob);
        setImageSrc(blobUrl);
      })
      .catch(() => {
        if (!cancelled) {
          setImageSrc("/space-bg.jpg");
        }
      });

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -10,
        overflow: "hidden",
        pointerEvents: "none",
        background: "#080c14",
      }}
    >
      <ErrorBoundary>
        <div style={{ position: "absolute", inset: 0 }}>
          <GridDistortion
            imageSrc={imageSrc}
            grid={12}
            mouse={0.28}
            strength={0.28}
            relaxation={0.92}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
