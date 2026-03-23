import { type ReactNode, useState } from "react";
import { Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface HintBannerProps {
  children: ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  className?: string;
}

export function HintBanner({
  children,
  dismissible = false,
  onDismiss,
  className,
}: HintBannerProps) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  const handleDismiss = () => {
    setVisible(false);
    onDismiss?.();
  };

  return (
    <div
      className={cn(
        "relative rounded-lg px-4 py-3 flex items-start gap-3",
        "backdrop-blur-xl bg-white/60 dark:bg-gray-900/60",
        "border border-white/20 dark:border-gray-700/30",
        "shadow-sm",
        className,
      )}
    >
      <Info className="h-4 w-4 mt-0.5 shrink-0 text-blue-500 dark:text-blue-400" />
      <div className="flex-1 text-sm text-foreground/80">{children}</div>
      {dismissible && (
        <button
          type="button"
          onClick={handleDismiss}
          className="shrink-0 rounded-md p-0.5 hover:bg-black/5 dark:hover:bg-white/10 transition-colors"
        >
          <X className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      )}
    </div>
  );
}
