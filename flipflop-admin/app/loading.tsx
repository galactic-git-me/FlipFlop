import { BrandCubeLoader } from "@/components/ui/brand-cube-loader";

export default function Loading() {
  return (
    <div className="flex h-full min-h-[60vh] w-full items-center justify-center">
      <BrandCubeLoader />
    </div>
  );
}
