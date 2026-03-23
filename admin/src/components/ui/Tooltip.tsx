import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Tooltip({ content, className, children }: TooltipProps) {
  return (
    <span className={cn("relative inline-flex group", className)}>
      <span tabIndex={0} className="outline-none">
        {children}
      </span>
      <span
        role="tooltip"
        className={cn(
          "absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2",
          "w-56 px-3 py-2 rounded-lg text-xs leading-relaxed",
          "bg-white/70 dark:bg-zinc-900/75 backdrop-blur-xl backdrop-saturate-150",
          "text-foreground border border-white/30 dark:border-white/10",
          "shadow-lg shadow-black/10 dark:shadow-black/30",
          "opacity-0 pointer-events-none scale-95",
          "transition-all duration-150",
          "group-hover:opacity-100 group-hover:pointer-events-auto group-hover:scale-100",
          "group-focus-within:opacity-100 group-focus-within:pointer-events-auto group-focus-within:scale-100",
        )}
      >
        {content}
      </span>
    </span>
  );
}
