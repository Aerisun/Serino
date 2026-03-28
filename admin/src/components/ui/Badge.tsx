import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants: Record<string, string> = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-secondary text-secondary-foreground",
  destructive: "bg-destructive text-destructive-foreground",
  outline: "border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] text-foreground bg-[rgb(var(--admin-surface-1)/0.32)]",
  success:
    "bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300",
  info: "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300",
  warning: "bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 border-amber-200/70 dark:border-amber-700/50",
};

interface BadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof badgeVariants;
}

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  return (
    <div
      className={cn(
        "admin-transition-fast inline-flex items-center rounded-full border border-[rgba(var(--admin-border-subtle)/0.22)] bg-[rgb(var(--admin-surface-1)/0.44)] backdrop-blur-sm px-2.5 py-1 text-xs font-semibold transition-[background-color,border-color,color,box-shadow]",
        badgeVariants[variant] || badgeVariants.default,
        className,
      )}
      {...props}
    />
  );
}
