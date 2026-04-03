import type { ReactNode } from "react";
import { Archive, LogOut, Send } from "lucide-react";
import { StatusVisibilityPills } from "@/components/StatusVisibilityPills";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";

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

  return (
    <div className="flex flex-wrap items-center gap-2">
      <StatusVisibilityPills
        visibility={visibility}
        onToggleVisibility={onToggleVisibility}
      />
      {extraActions}
      <Button
        type="button"
        variant="secondary"
        className={draftButtonClassName}
        onClick={onExit}
        disabled={isSaving}
      >
        <LogOut className="mr-2 h-4 w-4" />
        {isSaving ? t("common.saving") : t("common.exit")}
      </Button>
      <Button
        type="button"
        variant="secondary"
        className={isPublic ? publishButtonClassName : archiveButtonClassName}
        onClick={onConfirm}
        disabled={isSaving}
      >
        <ConfirmIcon className="mr-2 h-4 w-4" />
        {isSaving ? t("common.saving") : confirmLabel}
      </Button>
    </div>
  );
}
