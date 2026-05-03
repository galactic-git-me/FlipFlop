"use client";

import dynamic from "next/dynamic";

// WebGL canvas — must be loaded client-side only (no SSR)
const PixelBlast = dynamic(() => import("./PixelBlast"), { ssr: false });

export function TraeBg() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -10,
        pointerEvents: "none",
        background: "#080c14",
      }}
    >
      <PixelBlast
        variant="diamond"
        pixelSize={3}
        color="#2368be"
        patternScale={5.25}
        patternDensity={1.4}
        pixelSizeJitter={0}
        enableRipples
        rippleSpeed={0.4}
        rippleThickness={0.12}
        rippleIntensityScale={1.5}
        liquid={false}
        liquidStrength={0.12}
        liquidRadius={1.2}
        liquidWobbleSpeed={5}
        speed={1.55}
        edgeFade={0.25}
        transparent
      />
    </div>
  );
}
