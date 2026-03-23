import { Tooltip } from "./Tooltip";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface HelpIconProps {
  tip: ReactNode;
  className?: string;
}

export function HelpIcon({ tip, className }: HelpIconProps) {
  return (
    <Tooltip content={tip}>
      <span
        className={cn(
          "inline-flex items-center justify-center",
          "h-4 w-4 rounded-full border border-muted-foreground/40",
          "text-[10px] leading-none text-muted-foreground",
          "cursor-help select-none shrink-0",
          className,
        )}
        aria-label="帮助"
      >
        i
      </span>
    </Tooltip>
  );
}
