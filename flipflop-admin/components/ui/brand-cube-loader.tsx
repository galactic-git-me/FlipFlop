import { cn } from "@/lib/utils";
import { StrokeDrawType } from "@/components/ui/SignatureText";

type BrandCubeLoaderProps = {
  className?: string;
  size?: "xs" | "sm" | "md" | "lg";
};

/** FlipFlop-branded, scaled-down copy of MAC on-the.trading's startup cube. */
export function BrandCubeLoader({
  className,
  size = "md",
}: BrandCubeLoaderProps) {
  const dimensions = { xs: 40, sm: 88, md: 132, lg: 198 };

  const signatureSizes = { xs: 25, sm: 34, md: 46, lg: 58 };

  return (
    <div role="status" aria-live="polite" className={cn("flex min-w-0 flex-col items-center justify-center gap-1 overflow-x-hidden text-slate-100", className)}>
      <iframe
        src="/HTMLComponents/Cube/Cube.html"
        title=""
        aria-hidden="true"
        tabIndex={-1}
        style={{ width: dimensions[size], height: dimensions[size] }}
        className="shrink-0 border-0 bg-transparent"
      />
      <StrokeDrawType
        text="Loading....."
        trigger="loop"
        duration={1.15}
        stagger={0.075}
        hold={0.55}
        fontSize={signatureSizes[size]}
        fontWeight={500}
        fontFamily={'"FlipFlopNASA", sans-serif'}
        letterSpacing={0.22}
        ariaLabel="Loading"
        className="w-full min-w-0 max-w-[340px] overflow-x-hidden px-3"
      />
    </div>
  );
}
