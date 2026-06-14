import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md" | "lg";
}

const variantStyles = {
  primary: "bg-[#00dc82] text-[#080c14] hover:bg-[#00c472] font-semibold shadow-[0_0_16px_rgba(0,220,130,0.25)]",
  secondary: "bg-[#0d1320] text-white hover:bg-[#131d2e] border border-[#2d4a6b]",
  ghost: "text-white hover:text-white hover:bg-white/10",
  danger: "bg-red-600/20 text-white hover:bg-red-600/30 border border-red-500/40",
  outline: "bg-[#0d1320] border border-[#2d4a6b] text-white hover:border-[#00dc82]/50 hover:text-[#00dc82]",
};

const sizeStyles = {
  sm: "text-xs px-3 py-1.5 rounded-lg",
  md: "text-sm px-4 py-2 rounded-lg",
  lg: "text-sm px-6 py-2.5 rounded-xl",
};

export function Button({ variant = "secondary", size = "md", className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center gap-2 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
