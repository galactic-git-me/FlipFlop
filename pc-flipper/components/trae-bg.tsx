"use client";

import dynamic from "next/dynamic";

const GridDistortion = dynamic(() => import("./GridDistortion"), { ssr: false });

export function TraeBg() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -10,
        pointerEvents: "none",
      }}
    >
      <GridDistortion
        imageSrc="https://picsum.photos/1920/1080?grayscale"
        grid={10}
        mouse={0.1}
        strength={0.15}
        relaxation={0.9}
      />
    </div>
  );
}
