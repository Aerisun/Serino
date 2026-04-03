import type { ReactNode } from "react";
import type { AgentWorkflowCatalog, AgentWorkflowCatalogNodeType } from "@/pages/automation/api";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import type { Lang } from "@/i18n";
import { friendlyNodeTypeLabel, type WorkflowCanvasNode } from "../workflow-editor-types";
import { GenericSchemaInspector } from "./GenericSchemaInspector";

interface TriggerInspectorProps {
  lang: Lang;
  catalog: AgentWorkflowCatalog | undefined;
  selectedNode: WorkflowCanvasNode;
  triggerTypeOptions: AgentWorkflowCatalogNodeType[];
  switchTriggerType: (nextType: string) => void;
  selectedNodePrimaryFields: [string, Record<string, unknown>][];
  selectedNodeAdvancedFields: [string, Record<string, unknown>][];
  renderSchemaField: (
    fieldName: string,
    schema: Record<string, unknown>,
  ) => ReactNode;
  copy: {
    essentials: string;
    advanced: string;
  };
}

export function TriggerInspector({
  lang,
  catalog,
  selectedNode,
  triggerTypeOptions,
  switchTriggerType,
  selectedNodePrimaryFields,
  selectedNodeAdvancedFields,
  renderSchemaField,
  copy,
}: TriggerInspectorProps) {
  return (
    <>
      <div className="space-y-2">
        <LabelWithHelp
          label={lang === "zh" ? "触发方式" : "Trigger Type"}
          description={
            lang === "zh"
              ? "选择这一步怎么触发。切换后，图标和默认设置会一起更新。"
              : "Choose whether this trigger node is event-based, webhook-based, scheduled, or manual. The icon and default config update together."
          }
        />
        <Select
          value={selectedNode.data.nodeType}
          onValueChange={switchTriggerType}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {triggerTypeOptions.map((item) => (
              <SelectItem key={item.type} value={item.type}>
                {friendlyNodeTypeLabel(item.type, catalog, lang)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <GenericSchemaInspector
        copy={copy}
        selectedNodePrimaryFields={selectedNodePrimaryFields}
        selectedNodeAdvancedFields={selectedNodeAdvancedFields}
        renderSchemaField={renderSchemaField}
      />
    </>
  );
}
