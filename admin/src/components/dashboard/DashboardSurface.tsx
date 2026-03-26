import type { HTMLAttributes } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface DashboardSurfaceProps extends HTMLAttributes<HTMLDivElement> {
  eyebrow?: string;
  title: string;
  description?: string;
  contentClassName?: string;
}

export function DashboardSurface({
  eyebrow,
  title,
  description,
  className,
  contentClassName,
  children,
  ...props
}: DashboardSurfaceProps) {
  return (
    <Card
      className={cn(
        "overflow-hidden rounded-[26px] border border-black/5 bg-white/56 shadow-[0_10px_30px_rgba(15,23,42,0.04)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.03] dark:shadow-none",
        className,
      )}
      {...props}
    >
      <CardHeader className="gap-2 pb-4">
        {eyebrow ? (
          <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)]">
            {eyebrow}
          </span>
        ) : null}
        <div className="space-y-1">
          <CardTitle className="text-lg font-semibold tracking-tight text-foreground/95">{title}</CardTitle>
          {description ? <p className="text-sm leading-6 text-muted-foreground/88">{description}</p> : null}
        </div>
      </CardHeader>
      <CardContent className={cn("pt-0", contentClassName)}>{children}</CardContent>
    </Card>
  );
}
