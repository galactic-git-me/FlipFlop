"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { ErrorBoundary } from "./error-boundary";

// Start downloading the JS module immediately, in parallel with the image fetch
const modulePromise = import("./GridDistortion");
const GridDistortion = dynamic(() => modulePromise, { ssr: false });

export function TraeBg() {
  const [imageSrc, setImageSrc] = useState<string | null>(null);

  useEffect(() => {
    let blobUrl: string | null = null;

    fetch("/api/nasa-bg")
      .then((r) => r.blob())
      .then((blob) => {
        blobUrl = URL.createObjectURL(blob);
        setImageSrc(blobUrl);
      })
      .catch(() => setImageSrc("/space-bg.jpg"));

    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -10,
        background: "#080c14",
      }}
    >
      <ErrorBoundary>
        {imageSrc && (
          <GridDistortion
            imageSrc={imageSrc}
            grid={10}
            mouse={0.1}
            strength={0.15}
            relaxation={0.9}
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
