import { Loader2, Save } from "lucide-react";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { Button, type ButtonProps } from "@/components/ui/Button";

export function PendingSaveBadge({ className }: { className?: string }) {
  const { t } = useI18n();

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[rgb(var(--admin-accent-rgb)/0.18)] bg-[rgb(var(--admin-accent-rgb)/0.1)] px-2.5 py-1 text-[11px] font-medium text-[rgb(var(--admin-accent-rgb)/0.96)]",
        className,
      )}
    >
      {t("common.pendingSave")}
    </span>
  );
}

interface DirtySaveButtonProps extends Omit<ButtonProps, "children" | "variant"> {
  dirty: boolean;
  saving?: boolean;
}

export function DirtySaveButton({
  dirty,
  saving = false,
  size = "sm",
  className,
  disabled,
  ...props
}: DirtySaveButtonProps) {
  const { t } = useI18n();

  return (
    <Button
      type="button"
      size={size}
      variant={dirty ? "default" : "outline"}
      disabled={!dirty || saving || disabled}
      className={cn("gap-2", className)}
      {...props}
    >
      {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
      {saving ? t("common.saving") : t("common.save")}
    </Button>
  );
}
