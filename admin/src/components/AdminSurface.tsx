import type { HTMLAttributes, ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle, type CardProps } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface AdminSurfaceProps extends Omit<CardProps, "title"> {
  eyebrow?: ReactNode;
  title?: ReactNode;
  titleAccessory?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  contentClassName?: string;
  headerClassName?: string;
}

export function AdminSurface({
  eyebrow,
  title,
  titleAccessory,
  description,
  actions,
  className,
  contentClassName,
  headerClassName,
  children,
  surface = "default",
  ...props
}: AdminSurfaceProps) {
  const hasHeader = eyebrow || title || titleAccessory || description || actions;

  return (
    <Card
      surface={surface}
      className={cn("overflow-hidden rounded-[var(--admin-radius-xl)] shadow-[var(--admin-shadow-sm)]", className)}
      {...props}
    >
      {hasHeader ? (
        <CardHeader className={cn("gap-3 pb-4", headerClassName)}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1.5">
              {eyebrow ? (
                <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-[rgb(var(--admin-accent-rgb)/0.78)]">
                  {eyebrow}
                </div>
              ) : null}
              {title ? (
                <CardTitle className="text-lg font-semibold tracking-tight text-foreground/95">
                  <span className="inline-flex items-center gap-2">
                    <span>{title}</span>
                    {titleAccessory ? <span className="flex shrink-0 items-center">{titleAccessory}</span> : null}
                  </span>
                </CardTitle>
              ) : null}
              {description ? (
                <p className="max-w-3xl text-sm leading-6 text-muted-foreground/90">{description}</p>
              ) : null}
            </div>
            {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
          </div>
        </CardHeader>
      ) : null}
      <CardContent className={cn(hasHeader ? "pt-0" : "pt-6", contentClassName)}>{children}</CardContent>
    </Card>
  );
}

interface AdminToolbarProps extends HTMLAttributes<HTMLDivElement> {
  align?: "start" | "between";
}

export function AdminToolbar({ align = "between", className, ...props }: AdminToolbarProps) {
  return (
    <div
      className={cn(
        "admin-glass flex flex-col gap-3 rounded-[var(--admin-radius-lg)] px-4 py-4 sm:flex-row sm:flex-wrap sm:items-center",
        align === "between" && "sm:justify-between",
        className,
      )}
      {...props}
    />
  );
}
