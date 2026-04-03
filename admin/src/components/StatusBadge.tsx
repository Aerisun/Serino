import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/i18n";

const statusVariantMap: Record<string, string> = {
  draft: "secondary",
  published: "success",
  archived: "info",
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  active: "success",
  lost: "destructive",
  invalid: "destructive",
  unconfigured: "secondary",
  inactive: "secondary",
  queued: "warning",
  running: "info",
  retrying: "warning",
  paused: "secondary",
  completed: "success",
  failed: "destructive",
  cancelled: "secondary",
  restoring: "warning",
  public: "success",
  private: "info",
  unlisted: "outline",
};

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const variant = statusVariantMap[status] || "outline";
  const label = t(`status.${status}`);
  return <Badge variant={variant as any}>{label}</Badge>;
}
