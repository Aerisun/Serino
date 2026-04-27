import type { ReactNode } from "react";
import { Archive, LogOut, Send } from "lucide-react";
import { StatusVisibilityPills } from "@/components/StatusVisibilityPills";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

type ContentVisibility = "public" | "private";

interface ContentEditorHeaderActionsProps {
  visibility: ContentVisibility;
  isSaving: boolean;
  onToggleVisibility: () => void;
  onExit: () => void;
  onConfirm: () => void;
  extraActions?: ReactNode;
}

const draftButtonClassName =
  "bg-slate-100 text-slate-900 border-slate-200 shadow-none backdrop-blur-0 ring-0 hover:bg-slate-200 hover:text-slate-950 dark:bg-slate-800/80 dark:text-slate-100 dark:border-slate-700 dark:hover:bg-slate-800";

const publishButtonClassName =
  "bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700 hover:text-white dark:bg-emerald-500 dark:text-white dark:hover:bg-emerald-400";

const archiveButtonClassName =
  "bg-amber-500 text-white border-amber-500 hover:bg-amber-600 hover:text-white dark:bg-amber-500 dark:text-white dark:hover:bg-amber-400";

export function ContentEditorHeaderActions({
  visibility,
  isSaving,
  onToggleVisibility,
  onExit,
  onConfirm,
  extraActions,
}: ContentEditorHeaderActionsProps) {
  const { t, lang } = useI18n();
  const isPublic = visibility === "public";
  const confirmLabel = isPublic
    ? lang === "zh"
      ? "发布"
      : "Publish"
    : lang === "zh"
      ? "存档"
      : "Archive";
  const ConfirmIcon = isPublic ? Send : Archive;
  const hasExtraActions = extraActions != null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2",
        hasExtraActions &&
          "grid w-full grid-cols-[auto_auto] justify-start items-center sm:flex sm:w-auto sm:flex-wrap sm:items-center",
      )}
    >
      <div
        className={cn(
          hasExtraActions &&
            "order-3 sm:order-1",
        )}
      >
        <StatusVisibilityPills
          visibility={visibility}
          onToggleVisibility={onToggleVisibility}
        />
      </div>
      {extraActions ? (
        <div className="order-1 sm:order-2">
          {extraActions}
        </div>
      ) : null}
      <Button
        type="button"
        variant="secondary"
        className={cn(
          draftButtonClassName,
          hasExtraActions && "order-2 sm:order-3",
        )}
        onClick={onExit}
        disabled={isSaving}
      >
        <LogOut className="mr-2 h-4 w-4" />
        {isSaving ? t("common.saving") : t("common.exit")}
      </Button>
      <Button
        type="button"
        variant="secondary"
        className={cn(
          isPublic ? publishButtonClassName : archiveButtonClassName,
          hasExtraActions && "order-4",
        )}
        onClick={onConfirm}
        disabled={isSaving}
      >
        <ConfirmIcon className="mr-2 h-4 w-4" />
        {isSaving ? t("common.saving") : confirmLabel}
      </Button>
    </div>
  );
}
