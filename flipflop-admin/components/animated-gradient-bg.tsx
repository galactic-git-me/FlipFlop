"use client";

/**
 * AnimatedGradientBackground -- large, softly-blurred colour blobs that
 * slowly drift and pulse behind page content (the "moving gradient
 * background" pattern). Pure CSS animation, no canvas/JS render loop, so it
 * costs nothing at rest and doesn't compete with anything else on the page
 * for CPU. Colours are configurable via the `colors` prop; the default is
 * FlipFlop's own brand orange + blue (matching the logo).
 */

const DEFAULT_COLORS = ["#ff6a00", "#1e7bff", "#ff8a2e", "#4d9aff"];

export interface AnimatedGradientBackgroundProps {
  /** Blob colours, cycled across the blobs. Defaults to brand orange + blue. */
  colors?: string[];
  /** Background base colour behind the blobs. */
  baseColor?: string;
  /** 0-1, how visible the blobs are. Lower = more subtle. */
  opacity?: number;
  className?: string;
}

export function AnimatedGradientBackground({
  colors = DEFAULT_COLORS,
  baseColor = "#080c14",
  opacity = 0.55,
  className = "",
}: AnimatedGradientBackgroundProps) {
  const blobs = [
    { top: "5%", left: "10%", size: "50vmax", duration: "26s", delay: "0s" },
    { top: "55%", left: "65%", size: "60vmax", duration: "32s", delay: "-8s" },
    { top: "70%", left: "5%", size: "45vmax", duration: "24s", delay: "-14s" },
    { top: "10%", left: "70%", size: "40vmax", duration: "30s", delay: "-20s" },
  ];

  return (
    <div
      className={`agb-root ${className}`}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -10,
        overflow: "hidden",
        pointerEvents: "none",
        background: baseColor,
      }}
    >
      {blobs.map((blob, i) => (
        <div
          key={i}
          className="agb-blob"
          style={{
            position: "absolute",
            top: blob.top,
            left: blob.left,
            width: blob.size,
            height: blob.size,
            borderRadius: "50%",
            background: colors[i % colors.length],
            opacity,
            filter: "blur(120px)",
            animationDuration: blob.duration,
            animationDelay: blob.delay,
          }}
        />
      ))}
      <style>{`
        .agb-blob {
          animation-name: agb-drift;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
          animation-direction: alternate;
          will-change: transform;
        }
        @keyframes agb-drift {
          0% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(6vw, -4vh) scale(1.15); }
          100% { transform: translate(-5vw, 5vh) scale(0.95); }
        }
        @media (prefers-reduced-motion: reduce) {
          .agb-blob { animation: none; }
        }
      `}</style>
    </div>
  );
}
