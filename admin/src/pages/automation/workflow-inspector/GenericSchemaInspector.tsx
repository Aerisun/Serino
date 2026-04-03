import type { ReactNode } from "react";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import type { CopyShape } from "../workflow-editor-types";

interface GenericSchemaInspectorProps {
  copy: CopyShape;
  selectedNodePrimaryFields: [string, Record<string, unknown>][];
  selectedNodeAdvancedFields: [string, Record<string, unknown>][];
  showAdvanced?: boolean;
  renderSchemaField: (
    fieldName: string,
    schema: Record<string, unknown>,
  ) => ReactNode;
}

export function GenericSchemaInspector({
  copy,
  selectedNodePrimaryFields,
  selectedNodeAdvancedFields,
  showAdvanced = true,
  renderSchemaField,
}: GenericSchemaInspectorProps) {
  return (
    <>
      {selectedNodePrimaryFields.length > 0 ? (
        <div className="space-y-3">
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {copy.essentials}
          </div>
          {selectedNodePrimaryFields.map(([fieldName, schema]) =>
            renderSchemaField(fieldName, schema),
          )}
        </div>
      ) : null}

      {showAdvanced && selectedNodeAdvancedFields.length > 0 ? (
        <CollapsibleSection
          title={copy.advanced}
          defaultOpen={false}
          badge={String(selectedNodeAdvancedFields.length)}
        >
          <div className="space-y-3">
            {selectedNodeAdvancedFields.map(([fieldName, schema]) =>
              renderSchemaField(fieldName, schema),
            )}
          </div>
        </CollapsibleSection>
      ) : null}
    </>
  );
}
