import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  secondary?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  secondary,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "mb-6 space-y-4 rounded-[var(--admin-radius-xl)] admin-glass px-6 py-5",
        className,
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="flex-1">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground/95">{title}</h1>
          {description ? (
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground/90">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex items-center gap-2 lg:ml-auto">{actions}</div> : null}
      </div>
      {secondary ? <div className="pt-2">{secondary}</div> : null}
    </div>
  );
}
