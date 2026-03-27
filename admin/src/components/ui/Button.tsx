import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "ghost" | "glass" | "toolbar";
  size?: "default" | "sm" | "lg" | "icon";
}

const variants: Record<string, string> = {
  default:
    "border border-transparent bg-primary text-primary-foreground shadow-[0_10px_24px_rgba(var(--admin-accent-rgb)/0.22)] hover:bg-primary/92",
  secondary:
    "border border-border/60 bg-secondary/85 text-secondary-foreground hover:bg-secondary",
  destructive:
    "border border-transparent bg-destructive text-destructive-foreground shadow-[0_10px_24px_rgba(239,68,68,0.2)] hover:bg-destructive/90",
  outline:
    "admin-glass-input bg-transparent hover:bg-white/55 dark:hover:bg-white/[0.08] hover:text-accent-foreground",
  ghost:
    "border border-transparent bg-transparent hover:bg-white/35 dark:hover:bg-white/[0.06] hover:text-accent-foreground",
  glass:
    "admin-glass border-[rgba(var(--admin-border-subtle)/0.18)] bg-[linear-gradient(135deg,rgb(var(--admin-surface-strong)/0.74),rgb(var(--admin-surface-1)/0.48))] text-foreground shadow-[var(--admin-shadow-sm)] hover:bg-[linear-gradient(135deg,rgb(var(--admin-surface-strong)/0.86),rgb(var(--admin-surface-1)/0.58))]",
  toolbar:
    "rounded-full border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.56)] text-muted-foreground shadow-none hover:bg-[rgb(var(--admin-surface-1)/0.8)] hover:text-foreground",
};

const sizes: Record<string, string> = {
  default: "h-10 px-4 py-2",
  sm: "h-9 rounded-[var(--admin-radius-sm)] px-3",
  lg: "h-11 rounded-[var(--admin-radius-md)] px-8",
  icon: "h-10 w-10",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "admin-transition-fast inline-flex min-h-[2.75rem] items-center justify-center whitespace-nowrap rounded-[var(--admin-radius-md)] text-sm font-medium ring-offset-background transition-[background-color,border-color,color,box-shadow,transform,opacity] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
