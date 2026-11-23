import { cn } from "@/lib/utils";

type BrandCubeLoaderProps = {
  label?: string;
  className?: string;
  size?: "xs" | "sm" | "md" | "lg";
};

/** FlipFlop-branded, scaled-down copy of MAC on-the.trading's startup cube. */
export function BrandCubeLoader({
  label = "Loading.....",
  className,
  size = "md",
}: BrandCubeLoaderProps) {
  const dimensions = { xs: 40, sm: 88, md: 132, lg: 198 };

  return (
    <div role="status" aria-live="polite" className={cn("inline-flex items-center gap-3 text-sm text-slate-300", className)}>
      <iframe
        src="/HTMLComponents/Cube/Cube.html"
        title=""
        aria-hidden="true"
        tabIndex={-1}
        style={{ width: dimensions[size], height: dimensions[size] }}
        className="shrink-0 border-0 bg-transparent"
      />
      <span>{label}</span>
    </div>
  );
}
