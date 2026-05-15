"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { ErrorBoundary } from "./error-boundary";

// Start downloading the JS module immediately, in parallel with the image fetch
const modulePromise = import("./GridDistortion");
const GridDistortion = dynamic(() => modulePromise, { ssr: false });

export function TraeBg() {
  const [imageSrc, setImageSrc] = useState<string>("/space-bg.jpg");
  const [distortionReady, setDistortionReady] = useState(false);

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
        setDistortionReady(false);
        setImageSrc(blobUrl);
      })
      .catch(() => {
        if (!cancelled) {
          setDistortionReady(false);
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
        zIndex: 0,
        pointerEvents: "none",
        background: "#080c14",
        backgroundImage: `url(${imageSrc})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <ErrorBoundary>
        <div style={{ opacity: distortionReady ? 1 : 0, transition: "opacity 260ms ease" }}>
          <GridDistortion
            imageSrc={imageSrc}
            grid={10}
            mouse={0.1}
            strength={0.15}
            relaxation={0.9}
            onTextureReady={setDistortionReady}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
