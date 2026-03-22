import { Button } from "@/components/ui/Button";
import { X } from "lucide-react";
import { useI18n } from "@/i18n";

interface BulkAction {
  label: string;
  onClick: () => void;
  variant?: "default" | "outline" | "destructive" | "ghost";
}

interface BulkActionBarProps {
  selectedCount: number;
  onClearSelection: () => void;
  actions: BulkAction[];
}

export function BulkActionBar({ selectedCount, onClearSelection, actions }: BulkActionBarProps) {
  const { t } = useI18n();

  if (selectedCount === 0) return null;

  return (
    <div className="flex items-center gap-3 rounded-lg border bg-accent/50 px-4 py-2 mb-4">
      <span className="text-sm font-medium">
        {t("common.selected").replace("{count}", String(selectedCount))}
      </span>
      <div className="flex items-center gap-2 ml-auto">
        {actions.map((action, i) => (
          <Button key={i} size="sm" variant={action.variant || "outline"} onClick={action.onClick}>
            {action.label}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={onClearSelection}>
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
