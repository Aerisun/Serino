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
    "border-black/5 bg-white/46 text-foreground/90 shadow-none dark:border-white/10 dark:bg-white/[0.028]",
  accent:
    "border-[rgb(var(--shiro-border-rgb,185_194_211)/0.42)] bg-[rgb(var(--shiro-panel-rgb,239_248_249)/0.46)] text-foreground/90 shadow-none dark:border-[rgb(var(--shiro-border-rgb,109_69_79)/0.38)] dark:bg-[rgb(var(--shiro-panel-rgb,52_40_49)/0.24)]",
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
        "group relative overflow-hidden rounded-[22px] border p-4 transition-colors duration-200",
        toneClasses[tone],
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
          <Icon className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.82)]" />
        </div>
      </div>
    </div>
  );
}
