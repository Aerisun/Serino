import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { AlertTriangle } from "lucide-react";
import { useI18n } from "@/i18n";

interface ConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  variant?: "default" | "destructive";
  isPending?: boolean;
}

export function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title,
  description,
  confirmLabel,
  variant = "default",
  isPending = false,
}: ConfirmDialogProps) {
  const { t } = useI18n();

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent hideCloseButton className="max-w-[420px] rounded-2xl p-0 overflow-hidden">
        <div className="border-b border-white/10 px-6 pb-4 pt-5 dark:border-white/5">
          <div className="flex items-start gap-4">
            {variant === "destructive" && (
              <div className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-destructive/10 ring-1 ring-destructive/20">
                <AlertTriangle className="h-5 w-5 text-destructive" />
              </div>
            )}
            <DialogHeader className="flex-1 space-y-2 text-left">
              <DialogTitle className="text-base font-semibold tracking-tight">
                {title}
              </DialogTitle>
              {description && (
                <DialogDescription className="leading-6">
                  {description}
                </DialogDescription>
              )}
            </DialogHeader>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4">
          <Button
            variant="outline"
            className="min-w-20"
            onClick={onCancel}
            disabled={isPending}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant={variant === "destructive" ? "destructive" : "default"}
            className="min-w-20"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? t("common.loading") : confirmLabel || t("common.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
