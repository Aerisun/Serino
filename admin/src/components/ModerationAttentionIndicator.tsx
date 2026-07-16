import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";

interface ModerationAttentionIndicatorProps {
  pending: number;
  unread: number;
  compact?: boolean;
  className?: string;
}

export function ModerationAttentionIndicator({
  pending,
  unread,
  compact = false,
  className,
}: ModerationAttentionIndicatorProps) {
  const { t } = useI18n();

  if (pending <= 0 && unread <= 0) {
    return null;
  }

  const isPending = pending > 0;
  const count = isPending ? pending : unread;
  const label = isPending
    ? t("moderation.attentionPending", { count })
    : t("moderation.attentionUnread", { count });

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1",
        compact && "absolute -right-3 -top-2",
        className,
      )}
      aria-label={label}
      title={label}
    >
      <span
        className={cn(
          "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[11px] font-semibold tabular-nums shadow-sm",
          isPending
            ? "bg-destructive text-destructive-foreground"
            : "bg-amber-400 text-amber-950",
        )}
      >
        {count}
      </span>
    </span>
  );
}
