"use client";

import Image from "next/image";

// Cubic bezier ellipse tracing the orbital ring clockwise,
// starting at the red dot's resting position (top of the ring).
// Coordinates are in the 1442×567 logo image space.
const ORBITAL_PATH =
  "M 560,102" +
  " C 920,50 1385,115 1392,310" +
  " C 1399,505 1130,510 870,488" +
  " C 610,466 46,415 46,328" +
  " C 46,200 215,68 560,102" +
  " Z";

interface LogoAnimationProps {
  className?: string;
}

export default function LogoAnimation({ className }: LogoAnimationProps) {
  return (
    <div
      className={`relative ${className ?? ""}`}
      style={{ aspectRatio: "1442 / 567" }}
    >
      <Image
        src="/pics/logo_simple_no_bg.png"
        alt="FlipFlop"
        fill
        className="object-contain"
        priority
      />
      <svg
        viewBox="0 0 1442 567"
        className="absolute inset-0 w-full h-full"
        aria-hidden="true"
      >
        <defs>
          <path id="ff-orbital" d={ORBITAL_PATH} />
        </defs>
        <circle r="24" fill="#dd1111">
          <animateMotion
            dur="4s"
            repeatCount="indefinite"
            rotate="false"
            calcMode="linear"
          >
            <mpath href="#ff-orbital" />
          </animateMotion>
        </circle>
      </svg>
    </div>
  );
}
