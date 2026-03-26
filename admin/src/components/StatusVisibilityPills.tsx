import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { ArrowLeftRight } from "lucide-react";

type ContentVisibility = "public" | "private";

interface StatusVisibilityPillsProps {
  visibility: ContentVisibility;
  onToggleVisibility: () => void;
  className?: string;
}

const visibilityToneClasses: Record<ContentVisibility, string> = {
  public:
    "bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900/40 dark:text-green-300",
  private:
    "bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300",
};

export function StatusVisibilityPills({
  visibility,
  onToggleVisibility,
  className,
}: StatusVisibilityPillsProps) {
  const { t } = useI18n();

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-white/20 dark:border-white/10 backdrop-blur-sm p-1",
        className,
      )}
    >
      <Button
        type="button"
        size="sm"
        className={cn(
          "min-w-[132px] justify-between rounded-full border px-4 py-2.5 shadow-none transition-colors duration-200",
          visibilityToneClasses[visibility],
        )}
        onClick={onToggleVisibility}
        aria-label={`${t("common.visibility")}：${t(`posts.${visibility}`)}，点击切换`}
      >
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-current/70" />
          <span className="font-semibold tracking-wide">{t(`posts.${visibility}`)}</span>
        </span>
        <ArrowLeftRight className="h-4 w-4 opacity-75" />
      </Button>
    </div>
  );
}