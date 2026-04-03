import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface AdminSegmentedFilterItem {
  value: string;
  label: ReactNode;
  badge?: ReactNode;
  disabled?: boolean;
}

interface AdminSegmentedFilterProps {
  value: string;
  onValueChange: (value: string) => void;
  items: AdminSegmentedFilterItem[];
  size?: "sm" | "md";
  placement?: "inline" | "below-header";
  width?: "content" | "full";
  tone?: "default" | "accent";
  className?: string;
}

export function AdminSegmentedFilter({
  value,
  onValueChange,
  items,
  size = "md",
  placement = "inline",
  width = "content",
  tone = "default",
  className,
}: AdminSegmentedFilterProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;

    const handleWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      event.preventDefault();
      node.scrollBy({ left: event.deltaY, behavior: "auto" });
    };

    node.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      node.removeEventListener("wheel", handleWheel);
    };
  }, []);

  return (
    <div
      ref={scrollRef}
      className={cn(
        "admin-glass overflow-x-auto overflow-y-hidden rounded-[var(--admin-radius-lg)] p-1 shadow-[var(--admin-shadow-xs)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        placement === "below-header" && "-mt-2",
        width === "content" ? "max-w-fit" : "w-full",
        className,
      )}
      role="tablist"
      aria-label="filters"
    >
      <div className="flex min-w-max flex-nowrap items-center gap-1">
        {items.map((item) => {
          const active = item.value === value;
          return (
            <button
              key={item.value}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={item.disabled}
              onClick={() => onValueChange(item.value)}
              className={cn(
                "admin-transition-fast inline-flex shrink-0 items-center gap-2 rounded-full border px-3.5 text-sm font-medium transition-[background-color,border-color,color,box-shadow,transform,opacity] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                size === "sm" ? "h-9" : "h-10",
                item.disabled && "opacity-50",
                active
                  ? tone === "accent"
                    ? "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[rgb(var(--admin-accent-rgb)/0.1)] text-[rgb(var(--admin-accent-rgb)/0.96)] shadow-[0_12px_30px_-20px_rgb(var(--admin-accent-rgb)/0.45)]"
                    : "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[rgb(var(--admin-surface-1)/0.82)] text-foreground shadow-[0_10px_26px_-18px_rgb(var(--admin-accent-rgb)/0.35)] dark:bg-white/[0.08]"
                  : "border-transparent text-muted-foreground hover:border-border/35 hover:bg-[rgb(var(--admin-surface-1)/0.52)] hover:text-foreground dark:hover:bg-white/[0.05]",
              )}
            >
              <span className="truncate">{item.label}</span>
              {item.badge ? <span className="text-xs text-current/60">{item.badge}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
