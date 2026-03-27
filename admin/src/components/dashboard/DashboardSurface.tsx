import type { HTMLAttributes } from "react";
import { AdminSurface } from "@/components/AdminSurface";
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
    <AdminSurface
      eyebrow={eyebrow}
      title={title}
      description={description}
      className={cn(className)}
      contentClassName={cn("pt-0", contentClassName)}
      {...props}
    >
      {children}
    </AdminSurface>
  );
}
