import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  compact?: boolean;
}

export function DashboardEmptyState({ title, description, compact = false }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex h-full min-h-[220px] flex-col items-center justify-center rounded-[24px] border border-dashed border-black/8 bg-black/[0.02] px-6 text-center dark:border-white/10 dark:bg-white/[0.02]",
        compact && "min-h-[160px]",
      )}
    >
      <div className="max-w-sm space-y-2">
        <p className="text-sm font-medium tracking-tight text-foreground/90">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export function DashboardSkeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-[24px] bg-black/[0.05] dark:bg-white/[0.06]", className)} />;
}
