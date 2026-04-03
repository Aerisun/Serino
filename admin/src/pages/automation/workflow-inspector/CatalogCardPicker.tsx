import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";

export interface CatalogCardPickerItem {
  key: string;
  label: string;
  description?: string;
  meta?: ReactNode;
}

export interface CatalogCardPickerGroup {
  key: string;
  label: string;
  items: CatalogCardPickerItem[];
}

interface CatalogCardPickerProps {
  mode: "single" | "multiple";
  groups: CatalogCardPickerGroup[];
  selectedKeys: string[];
  onChange: (nextKeys: string[]) => void;
  currentTitle?: string;
  currentEmptyText?: string;
  groupSelectedSuffix?: string;
  selectedSummaryTitle?: string;
}

export function CatalogCardPicker({
  mode,
  groups,
  selectedKeys,
  onChange,
  currentTitle,
  currentEmptyText,
  groupSelectedSuffix,
  selectedSummaryTitle,
}: CatalogCardPickerProps) {
  const selectedItems = groups.flatMap((group) =>
    group.items.filter((item) => selectedKeys.includes(item.key)),
  );

  return (
    <div className="space-y-3">
      {currentTitle ? (
        <div className="rounded-[16px] border border-border/60 bg-background/70 px-3 py-3 text-sm text-foreground">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {currentTitle}
          </div>
          {selectedItems.length > 0 ? (
            mode === "single" ? (
              <div className="mt-2 font-medium">{selectedItems[0]?.label}</div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedItems.map((item) => (
                  <Badge key={item.key} variant="secondary" className="gap-2 px-2 py-1">
                    <span>{item.label}</span>
                    {item.meta ? <span className="text-[10px] text-muted-foreground">{item.meta}</span> : null}
                  </Badge>
                ))}
              </div>
            )
          ) : (
            <div className="mt-2 text-xs leading-5 text-muted-foreground">{currentEmptyText || "-"}</div>
          )}
        </div>
      ) : null}

      <div className="space-y-3">
        {groups.map((group) => {
          const selectedCount = group.items.filter((item) => selectedKeys.includes(item.key)).length;
          return (
            <details
              key={group.key}
              className="group overflow-hidden rounded-[18px] border border-border/60 bg-background/70"
              open={selectedCount > 0}
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{group.label}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {group.items.length}
                    </Badge>
                    {selectedCount > 0 ? (
                      <Badge variant="secondary" className="text-[10px]">
                        {selectedCount}
                        {groupSelectedSuffix || ""}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
              </summary>
              <div className="border-t border-border/60 px-3 py-3">
                <div className="space-y-2">
                  {group.items.map((item) => {
                    const active = selectedKeys.includes(item.key);
                    return (
                      <div
                        key={item.key}
                        className={cn(
                          "rounded-[16px] border px-3 py-3 transition-colors",
                          active
                            ? "border-sky-400/60 bg-sky-500/10"
                            : "border-border/60 bg-background/80 hover:bg-background/95",
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <button
                            type="button"
                            onClick={() => {
                              if (mode === "single") {
                                onChange([item.key]);
                                return;
                              }
                              onChange(
                                active
                                  ? selectedKeys.filter((key) => key !== item.key)
                                  : [...selectedKeys, item.key],
                              );
                            }}
                            className="flex-1 text-left"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-sm font-medium text-foreground">{item.label}</div>
                              {item.meta ? <span className="text-[10px] text-muted-foreground">{item.meta}</span> : null}
                            </div>
                          </button>
                          {item.description ? (
                            <LabelWithHelp
                              hideLabel
                              label=""
                              title={item.label}
                              description={item.description}
                            />
                          ) : null}
                          {active ? (
                            <Badge variant="outline">
                              {mode === "single" ? "当前使用" : "已选"}
                            </Badge>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </details>
          );
        })}
      </div>

      {mode === "multiple" && selectedSummaryTitle && selectedItems.length > 0 ? (
        <div className="rounded-[18px] border border-border/60 bg-background/72 px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {selectedSummaryTitle}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedItems.map((item) => (
              <Badge key={`summary:${item.key}`} variant="secondary" className="gap-2 px-2 py-1">
                <span>{item.label}</span>
                {item.meta ? <span className="text-[10px] text-muted-foreground">{item.meta}</span> : null}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
