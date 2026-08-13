"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "flex items-center gap-1 overflow-x-auto border-b border-slate-800 pb-0",
        className
      )}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 text-xs font-semibold whitespace-nowrap border-b-2 border-transparent text-slate-500 transition-colors",
        "hover:text-slate-300",
        "data-[state=active]:text-[#00dc82] data-[state=active]:border-[#00dc82]",
        className
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn("flex flex-col gap-4 pt-4 outline-none", className)}
      {...props}
    />
  );
}
