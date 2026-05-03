import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info" | "muted";
  className?: string;
}

const variantStyles = {
  default: "bg-slate-700/50 text-slate-300 border-slate-600/50",
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  warning: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  danger: "bg-red-500/10 text-red-400 border-red-500/30",
  info: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  muted: "bg-slate-800/50 text-slate-500 border-slate-700/50",
};

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border",
      variantStyles[variant],
      className
    )}>
      {children}
    </span>
  );
}
