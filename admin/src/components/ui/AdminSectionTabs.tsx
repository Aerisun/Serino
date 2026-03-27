import { useRef, type ReactNode, type WheelEvent } from "react";
import { NavLink } from "react-router-dom";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface AdminSectionTabBaseItem {
  value: string;
  label: ReactNode;
  description?: ReactNode;
  icon?: LucideIcon;
  disabled?: boolean;
  badge?: ReactNode;
}

export interface AdminSectionTabLinkItem extends AdminSectionTabBaseItem {
  to: string;
  end?: boolean;
}

export interface AdminSectionTabValueItem extends AdminSectionTabBaseItem {
  to?: never;
  end?: never;
}

interface AdminSectionTabsBaseProps {
  variant?: "segmented" | "pill";
  size?: "sm" | "md";
  className?: string;
}

interface AdminSectionTabsLinkProps extends AdminSectionTabsBaseProps {
  items: readonly AdminSectionTabLinkItem[];
  value?: never;
  onValueChange?: never;
}

interface AdminSectionTabsValueProps extends AdminSectionTabsBaseProps {
  items: readonly AdminSectionTabValueItem[];
  value: string;
  onValueChange: (value: string) => void;
}

type AdminSectionTabsProps = AdminSectionTabsLinkProps | AdminSectionTabsValueProps;

function getItemClassName({
  active,
  disabled,
  size,
}: {
  active: boolean;
  disabled?: boolean;
  size: "sm" | "md";
}) {
  return cn(
    "group admin-transition-fast relative flex shrink-0 items-center gap-3 rounded-[calc(var(--admin-radius-lg)-0.15rem)] border border-transparent text-left transition-[background-color,color,box-shadow,transform,opacity]",
    size === "sm" ? "px-3 py-2" : "px-4 py-3",
    disabled && "pointer-events-none opacity-50",
    active
      ? "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[linear-gradient(135deg,rgb(var(--admin-accent-rgb)/0.18),rgb(var(--admin-glow-rgb)/0.14))] text-foreground shadow-[0_12px_30px_-18px_rgb(var(--admin-accent-rgb)/0.52)]"
      : "text-muted-foreground hover:border-border/30 hover:bg-[rgb(var(--admin-surface-1)/0.56)] hover:text-foreground dark:hover:bg-white/[0.05]",
  );
}

function SectionTabContent({
  item,
  active,
  size,
}: {
  item: AdminSectionTabBaseItem;
  active: boolean;
  size: "sm" | "md";
}) {
  const Icon = item.icon;

  return (
    <>
      {Icon ? (
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-[background-color,border-color,color]",
            size === "sm" && "h-9 w-9",
            active
              ? "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-background text-[rgb(var(--admin-accent-rgb)/0.96)]"
              : "border-border/60 bg-background/60 text-muted-foreground group-hover:text-foreground",
          )}
        >
          <Icon className={cn("h-4 w-4", size === "sm" && "h-3.5 w-3.5")} />
        </span>
      ) : null}

      <span className="min-w-0">
        <span className={cn("block truncate font-semibold tracking-tight", "text-sm")}>
          {item.label}
          {item.badge ? <span className="ml-2 align-middle">{item.badge}</span> : null}
        </span>
        {item.description ? (
          <span
            className={cn(
              "block truncate text-current/55",
              size === "sm" ? "text-[11px]" : "text-xs",
            )}
          >
            {item.description}
          </span>
        ) : null}
      </span>
    </>
  );
}

export function AdminSectionTabs(props: AdminSectionTabsProps) {
  const {
    items,
    variant = "segmented",
    size = "md",
    className,
  } = props;
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const isValueTabs = "onValueChange" in props;

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    const node = scrollRef.current;
    if (!node) return;
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    event.preventDefault();
    node.scrollBy({ left: event.deltaY, behavior: "auto" });
  };

  return (
    <div className={cn("relative", className)}>
      <div
        ref={scrollRef}
        onWheel={handleWheel}
        className="admin-glass overflow-x-auto overflow-y-hidden rounded-[var(--admin-radius-xl)] p-2 shadow-[var(--admin-shadow-sm)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <div
          className={cn(
            "flex min-w-max flex-nowrap gap-2",
            variant === "segmented" && "items-stretch",
          )}
        >
          {items.map((tab) => {
            if (isValueTabs) {
              const isActive = tab.value === props.value;
              return (
                <button
                  key={tab.value}
                  type="button"
                  disabled={tab.disabled}
                  aria-pressed={isActive}
                  onClick={() => props.onValueChange(tab.value)}
                  className={getItemClassName({
                    active: isActive,
                    disabled: tab.disabled,
                    size,
                  })}
                >
                  <SectionTabContent item={tab} active={isActive} size={size} />
                </button>
              );
            }

            const linkTab = tab as AdminSectionTabLinkItem;
            return (
              <NavLink
                key={linkTab.value}
                to={linkTab.to}
                end={linkTab.end}
                aria-disabled={linkTab.disabled}
                className={({ isActive }) =>
                  getItemClassName({
                    active: isActive,
                    disabled: linkTab.disabled,
                    size,
                  })
                }
              >
                {({ isActive }) => (
                  <SectionTabContent item={linkTab} active={isActive} size={size} />
                )}
              </NavLink>
            );
          })}
        </div>
      </div>
    </div>
  );
}
