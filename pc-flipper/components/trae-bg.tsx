"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "./error-boundary";

const GridDistortion = dynamic(() => import("./GridDistortion"), { ssr: false });

export function TraeBg() {
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
        <GridDistortion
          imageSrc="/api/nasa-bg"
          grid={10}
          mouse={0.1}
          strength={0.15}
          relaxation={0.9}
        />
      </ErrorBoundary>
    </div>
  );
}
