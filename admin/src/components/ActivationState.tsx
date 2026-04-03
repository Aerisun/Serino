import { type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export function inactiveRowClassName(isActive: boolean): string | undefined {
  return isActive
    ? undefined
    : "bg-muted/80 text-muted-foreground/90 hover:bg-muted/85 [&_td]:bg-muted/50 [&_td]:text-muted-foreground/90 [&_td]:opacity-70";
}

interface ActivationStateTextProps {
  inactive?: boolean;
  className?: string;
  children: ReactNode;
  as?: "span" | "div";
}

export function ActivationStateText({
  inactive = false,
  className,
  children,
  as: Tag = "span",
}: ActivationStateTextProps) {
  return <Tag className={cn(className, inactive && "text-muted-foreground/75 opacity-75")}>{children}</Tag>;
}

interface ActivationToggleButtonProps {
  isActive: boolean;
  disabled?: boolean;
  onClick: () => void;
  activeLabel: ReactNode;
  inactiveLabel: ReactNode;
  activeTitle?: string;
  inactiveTitle?: string;
  className?: string;
}

export function ActivationToggleButton({
  isActive,
  disabled,
  onClick,
  activeLabel,
  inactiveLabel,
  activeTitle,
  inactiveTitle,
  className,
}: ActivationToggleButtonProps) {
  return (
    <Button
      type="button"
      variant="toolbar"
      size="sm"
      className={cn(
        "min-h-0 h-6 min-w-[3rem] rounded-full px-2 text-sm font-medium",
        isActive
          ? "border-border/55 bg-[rgb(var(--admin-surface-1)/0.82)] text-foreground hover:bg-[rgb(var(--admin-surface-1)/0.94)]"
          : "border-amber-500/45 bg-amber-500/18 text-amber-800 hover:bg-amber-500/24 dark:border-amber-400/40 dark:text-amber-200",
        className,
      )}
      title={isActive ? activeTitle : inactiveTitle}
      disabled={disabled}
      onClick={onClick}
    >
      {isActive ? activeLabel : inactiveLabel}
    </Button>
  );
}
