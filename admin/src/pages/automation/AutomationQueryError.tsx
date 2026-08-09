import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function AutomationQueryError({
  lang,
  onRetry,
}: {
  lang: "zh" | "en";
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-[var(--admin-radius-lg)] border border-destructive/25 bg-destructive/[0.05] p-4 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3 text-destructive">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          {lang === "zh"
            ? "数据加载失败，请检查服务状态后重试。"
            : "Data failed to load. Check the service and try again."}
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {lang === "zh" ? "重新加载" : "Try again"}
      </Button>
    </div>
  );
}
