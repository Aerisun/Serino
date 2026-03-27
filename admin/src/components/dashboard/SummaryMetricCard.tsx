import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SummaryMetricCardProps {
  label: string;
  value: number | string;
  hint?: string;
  icon: LucideIcon;
  tone?: "default" | "accent" | "warning";
  className?: string;
}

const toneClasses: Record<NonNullable<SummaryMetricCardProps["tone"]>, string> = {
  default:
    "border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.46)] text-foreground/90 shadow-none dark:bg-white/[0.03]",
  accent:
    "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[linear-gradient(135deg,rgb(var(--admin-accent-rgb)/0.12),rgb(var(--admin-glow-rgb)/0.08))] text-foreground/92 shadow-[0_18px_46px_-28px_rgb(var(--admin-accent-rgb)/0.55)]",
  warning:
    "border-amber-200/70 bg-amber-50/68 text-amber-950 shadow-none dark:border-amber-400/20 dark:bg-amber-500/8 dark:text-amber-100",
};



export function SummaryMetricCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  className,
}: SummaryMetricCardProps) {
  return (
    <div
      className={cn(
        "admin-transition-fast group relative overflow-hidden rounded-[var(--admin-radius-lg)] border p-4 transition-[background-color,border-color,color,box-shadow,transform]",
        toneClasses[tone],
        "hover:bg-[rgb(var(--admin-surface-1)/0.66)] dark:hover:bg-white/[0.05]",
        className,
      )}
    >
      <div className="relative flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground/88">{label}</p>
          <p className="mt-2.5 text-[1.9rem] font-semibold tracking-tight text-foreground/95">{value}</p>
          {hint ? <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{hint}</p> : null}
        </div>
        <div className="rounded-full border border-black/5 bg-white/70 p-2 dark:border-white/10 dark:bg-white/[0.04]">
          <Icon className="h-4 w-4 text-[rgb(var(--admin-accent-rgb)/0.82)]" />
        </div>
      </div>
    </div>
  );
}
