import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants: Record<string, string> = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-secondary text-secondary-foreground",
  destructive: "bg-destructive text-destructive-foreground",
  outline: "text-foreground",
  success:
    "bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300",
  info: "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300",
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
        "inline-flex items-center rounded-full border border-white/20 dark:border-white/10 backdrop-blur-sm px-2.5 py-0.5 text-xs font-semibold transition-colors",
        badgeVariants[variant] || badgeVariants.default,
        className,
      )}
      {...props}
    />
  );
}
