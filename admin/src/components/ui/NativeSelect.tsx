import { ChevronDown } from "lucide-react";
import { forwardRef, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NativeSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  containerClassName?: string;
  iconClassName?: string;
  children: ReactNode;
}

export const NativeSelect = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, containerClassName, iconClassName, children, ...props }, ref) => (
    <div className={cn("relative flex w-full items-center", containerClassName)}>
      <select
        ref={ref}
        className={cn(
          "flex min-h-[2.75rem] w-full appearance-none rounded-[var(--admin-radius-md)] admin-glass-input px-3 py-2 pr-9 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className={cn(
          "pointer-events-none absolute right-3 h-4 w-4 text-muted-foreground/80",
          iconClassName,
        )}
      />
    </div>
  ),
);

NativeSelect.displayName = "NativeSelect";
