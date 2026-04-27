import type { AgentWorkflowCatalog, AgentWorkflowCatalogNodeType } from "@/pages/automation/api";
import { Button } from "@/components/ui/Button";
import type { Lang } from "@/i18n";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  type CopyShape,
  iconForName,
  friendlyCategoryLabel,
} from "./workflow-editor-core";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface WorkflowPaletteProps {
  show: boolean;
  onClose: () => void;
  paletteGroups: { category: string; items: AgentWorkflowCatalogNodeType[] }[];
  catalog: AgentWorkflowCatalog | undefined;
  lang: Lang;
  copy: CopyShape;
  onAddNode: (definition: AgentWorkflowCatalogNodeType) => void;
}

// ---------------------------------------------------------------------------
// WorkflowPalette component
// ---------------------------------------------------------------------------

export function WorkflowPalette({
  show,
  onClose,
  paletteGroups,
  catalog,
  lang,
  copy,
  onAddNode,
}: WorkflowPaletteProps) {
  const alwaysVisibleCategories = new Set(["common", "tool", "operation"]);
  const visibleGroups = paletteGroups.filter((group) =>
    alwaysVisibleCategories.has(group.category),
  );
  const advancedGroups = paletteGroups.filter(
    (group) => !alwaysVisibleCategories.has(group.category),
  );
  const advancedCount = advancedGroups.reduce((count, group) => count + group.items.length, 0);

  return (
    <div
      className={cn(
        "absolute bottom-4 left-4 top-[108px] z-40 flex w-[228px] flex-col overflow-hidden rounded-[28px] border border-border/60 bg-background/88 p-4 shadow-[var(--admin-shadow-lg)] backdrop-blur-xl transition-[transform,opacity] duration-200",
        show ? "translate-x-0 opacity-100" : "-translate-x-[calc(100%+1rem)] opacity-0 pointer-events-none",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {copy.palette}
          </div>
          <div className="mt-1 text-sm text-muted-foreground">{copy.addNode}</div>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onClose}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      <div className="mt-4 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {visibleGroups.map((group) => (
          <div key={group.category}>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {friendlyCategoryLabel(group.category, catalog, lang)}
            </div>
            <div className="grid gap-2">
              {group.items.map((item) => {
                const Icon = iconForName(item.icon);
                return (
                  <Button
                    key={item.type}
                    type="button"
                    variant="glass"
                    className="justify-start gap-2"
                    onClick={() => onAddNode(item)}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label || item.type}
                  </Button>
                );
              })}
            </div>
          </div>
        ))}

        {advancedGroups.length > 0 ? (
          <details className="group overflow-hidden rounded-[22px] border border-border/60 bg-background/70">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{copy.advanced}</span>
                  <span className="inline-flex items-center rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground">
                    {advancedCount}
                  </span>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
            </summary>

            <div className="border-t border-border/60 px-4 py-4">
              <div className="space-y-4">
                {advancedGroups.map((group) => (
                  <div key={group.category}>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      {friendlyCategoryLabel(group.category, catalog, lang)}
                    </div>
                    <div className="grid gap-2">
                      {group.items.map((item) => {
                        const Icon = iconForName(item.icon);
                        return (
                          <Button
                            key={item.type}
                            type="button"
                            variant="glass"
                            className="justify-start gap-2"
                            onClick={() => onAddNode(item)}
                          >
                            <Icon className="h-4 w-4" />
                            {item.label || item.type}
                          </Button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}
