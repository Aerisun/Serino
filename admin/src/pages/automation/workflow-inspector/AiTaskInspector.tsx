import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { Lang } from "@/i18n";
import {
  type AiTaskShellConfig,
  type CopyShape,
  type WorkflowCanvasNode,
  friendlyFieldLabel,
} from "../workflow-editor-types";
import type { DeriveAiSchemaResult } from "@/pages/automation/api";
import { ChevronRight } from "lucide-react";
import {
  describeAiApprovalMount,
  describeAiExtraMountBadge,
  describeAiDownstreamLabel,
  describeAiDownstreamPurpose,
  describeAiDownstreamRequirementText,
  describeAiExtraMountLabel,
  describeAiTriggerMount,
  describeAiUpstreamSlotSummary,
} from "../workflow-ai-io-copy";

interface AiTaskInspectorProps {
  lang: Lang;
  copy: CopyShape;
  selectedNode: WorkflowCanvasNode;
  mountedCapabilityItems: {
    key: string;
    label: string;
    kindLabel: string;
  }[];
  triggerEventOptions: {
    value: string;
    label: string;
    description?: string;
    target_types?: string[];
  }[];
  selectedNodePrimaryFields: [string, Record<string, unknown>][];
  selectedNodeAdvancedFields: [string, Record<string, unknown>][];
  renderSchemaField: (
    fieldName: string,
    schema: Record<string, unknown>,
  ) => ReactNode;
  aiShellConfig: AiTaskShellConfig | null;
  derivingSchema: boolean;
  derivedSchema: DeriveAiSchemaResult | null;
  derivedOutputSummary: string;
  derivedOutputFields: [string, Record<string, unknown>][];
  setNodeConfig: (key: string, value: unknown) => void;
}

export function AiTaskInspector({
  lang,
  copy,
  selectedNode,
  mountedCapabilityItems,
  triggerEventOptions,
  selectedNodePrimaryFields,
  selectedNodeAdvancedFields,
  renderSchemaField,
  aiShellConfig,
  derivingSchema,
  derivedSchema,
  derivedOutputSummary,
  derivedOutputFields,
  setNodeConfig,
}: AiTaskInspectorProps) {
  const contractContext = derivedSchema?.contract_context ?? {
    node_id: selectedNode.id,
    node_type: "ai.task",
    upstream_inputs: [],
    downstream_consumers: [],
    mounted_tools: [],
    mounted_actions: [],
    tool_usage_policy: {
      mode: String(selectedNode.data.config.tool_usage_mode || "recommended").trim() || "recommended",
      minimum_tool_calls: Math.max(1, Number(selectedNode.data.config.minimum_tool_calls || 1)),
    },
    output_contract: {
      summary: derivedOutputSummary,
      field_keys: derivedOutputFields.map(([fieldName]) => fieldName),
    },
  };

  const sectionTitle = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const sectionHint = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const triggerEventOptionByValue = new Map(
    triggerEventOptions.map((item) => [String(item.value || "").trim(), item]),
  );
  const localizeUpstreamSummary = (slot: (typeof contractContext.upstream_inputs)[number]) =>
    describeAiUpstreamSlotSummary(slot, lang);
  const localizeExtraMountLabel = (slot: (typeof contractContext.upstream_inputs)[number]) =>
    describeAiExtraMountLabel(slot, lang);
  const localizeExtraMountBadge = (slot: (typeof contractContext.upstream_inputs)[number]) => {
    if (slot.kind === "trigger" && slot.source.node_type === "trigger.event") {
      const matched = triggerEventOptionByValue.get(String(slot.source_summary || "").trim());
      if (matched?.label) return matched.label;
    }
    return describeAiExtraMountBadge(slot, lang);
  };
  const localizeExtraMountSummary = (slot: (typeof contractContext.upstream_inputs)[number]) => {
    if (slot.kind === "trigger") {
      if (slot.source.node_type === "trigger.event") {
        const matched = triggerEventOptionByValue.get(String(slot.source_summary || "").trim());
        if (matched?.description) return matched.description;
        if (matched?.label) return `触发条件：${matched.label}。`;
      }
      return describeAiTriggerMount(slot, lang);
    }
    if (slot.kind === "control") {
      return describeAiApprovalMount(slot, lang);
    }
    return slot.note.summary;
  };
  const localizeDownstreamLabel = (consumer: (typeof contractContext.downstream_consumers)[number]) =>
    describeAiDownstreamLabel(consumer, lang);
  const localizeDownstreamPurpose = (consumer: (typeof contractContext.downstream_consumers)[number]) =>
    describeAiDownstreamPurpose(consumer, lang);
  const localizeRequirement = (consumer: (typeof contractContext.downstream_consumers)[number]) =>
    describeAiDownstreamRequirementText(consumer, lang);
  const dataInputs = contractContext.upstream_inputs.filter((slot) => slot.kind === "data");
  const extraInputs = contractContext.upstream_inputs.filter((slot) => slot.kind !== "data");
  const outputGroups = Array.from(
    contractContext.downstream_consumers.reduce((map, consumer) => {
      const key = `${consumer.target_port.id}:${consumer.target_port.label}`;
      const list = map.get(key) || [];
      list.push(consumer);
      map.set(key, list);
      return map;
    }, new Map<string, typeof contractContext.downstream_consumers>()),
  ).map(([key, consumers]) => ({
    key,
    outputFields: Array.from(
      new Set(
        consumers.flatMap((consumer) => consumer.required_fields).filter((field) => field.trim().length > 0),
      ),
    ),
    consumers,
  }));

  return (
    <>
      <div className="space-y-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <LabelWithHelp
                label={lang === "zh" ? "运行模式" : "Execution Mode"}
                description={
                  lang === "zh"
                    ? "简单直流只跑一轮；循环调用会多轮处理。"
                    : "Direct runs once. Loop mode iterates with a notebook and tool feedback."
                }
              />
            </div>
            <div className="w-[180px] shrink-0">
              <Select
                value={aiShellConfig?.mode || "direct"}
                onValueChange={(value) => setNodeConfig("mode", value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="direct">
                    {lang === "zh" ? "简单直流" : "Direct"}
                  </SelectItem>
                  <SelectItem value="loop">
                    {lang === "zh" ? "循环调用" : "Loop"}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {aiShellConfig?.mode === "loop" ? (
            <div className="space-y-2">
              <LabelWithHelp
                label={lang === "zh" ? "最大轮次" : "Max Rounds"}
                description={
                  lang === "zh"
                    ? "超过这个次数还没收敛，就停止。"
                    : "Stops if the loop still has not converged."
                }
              />
              <Input
                type="number"
                min={1}
                max={20}
                value={String(aiShellConfig.loop_max_rounds)}
                onChange={(event) =>
                  setNodeConfig("loop_max_rounds", Number(event.target.value || 6))
                }
              />
            </div>
          ) : null}
          <div className="space-y-2">
            {selectedNodePrimaryFields
              .filter(([fieldName]) => fieldName === "instructions")
              .map(([fieldName, schema]) => renderSchemaField(fieldName, schema))}
          </div>
        </div>

        {dataInputs.length > 0 ? (
          <CollapsibleSection title={sectionTitle("输入挂载", "Input Mounts")}>
            <div className="space-y-3">
              {dataInputs.map((slot) => (
                <details
                  key={`${slot.kind}:${slot.slot}:${slot.source.node_label}`}
                  className="group overflow-hidden rounded-[18px] border border-border/60 bg-background/80"
                  open
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{slot.label}</span>
                        {slot.source.node_label ? <Badge variant="secondary">{slot.source.node_label}</Badge> : null}
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
                  </summary>
                  <div className="border-t border-border/60 px-4 py-3">
                    <div className="space-y-3">
                      <div className="text-sm text-foreground">{localizeUpstreamSummary(slot)}</div>
                      {slot.source_summary ? (
                        <div className="text-sm text-muted-foreground">{slot.source_summary}</div>
                      ) : null}
                      {slot.provided_fields.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {slot.provided_fields.map((field) => (
                            <Badge key={`${slot.slot}:${field}`} variant="outline">
                              {friendlyFieldLabel(field, lang)}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                      <div className="space-y-2">
                        <LabelWithHelp
                          label={lang === "zh" ? "输入口备注" : "Input Note"}
                          description={
                            lang === "zh"
                              ? "补一句这份输入该怎么用。"
                              : "This note is sent together with the input so the AI understands how to use it."
                          }
                        />
                        <Textarea
                          rows={3}
                          value={slot.note.operator_note}
                          onChange={(event) =>
                            setNodeConfig("input_slots", {
                              ...(aiShellConfig?.input_slots || {}),
                              [slot.slot]: { note: event.target.value },
                            })
                          }
                          placeholder={
                            lang === "zh"
                              ? "例如：这是上一个 AI 的总结，作为背景参考，不要逐字复述。"
                              : "For example: this is the previous AI summary, use it as background context rather than repeating it."
                          }
                        />
                      </div>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </CollapsibleSection>
        ) : null}

        {(extraInputs.length > 0 || mountedCapabilityItems.length > 0) ? (
          <CollapsibleSection title={sectionTitle("额外挂载", "Extra Mounts")}>
            <div className="space-y-3">
              {extraInputs.map((slot) => (
                <div
                  key={`${slot.kind}:${slot.slot}`}
                  className="rounded-[18px] border border-border/60 bg-background/80 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{localizeExtraMountLabel(slot)}</Badge>
                    <Badge variant="secondary">{localizeExtraMountBadge(slot)}</Badge>
                  </div>
                  <div className="mt-2 text-sm text-foreground">
                    {localizeExtraMountSummary(slot)}
                  </div>
                </div>
              ))}

              <div className="rounded-[18px] border border-border/60 bg-background/80 px-4 py-3">
                <div className="text-sm font-medium text-foreground">
                  {sectionTitle("挂载能力", "Mounted Capabilities")}
                </div>
                {mountedCapabilityItems.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {mountedCapabilityItems.map((item) => (
                      <div
                        key={item.key}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-[14px] border border-border/60 bg-background/95 px-3 py-2.5"
                      >
                        <span className="text-sm font-medium text-foreground">{item.label}</span>
                        <Badge variant="secondary">{item.kindLabel}</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-[14px] border border-border/60 bg-background/95 px-3 py-2 text-xs leading-5 text-muted-foreground">
                    {lang === "zh"
                      ? "当前还没有挂载任何额外挂载能力。"
                      : "No mounted capabilities are available yet."}
                  </div>
                )}
              </div>
            </div>
          </CollapsibleSection>
        ) : null}

        <CollapsibleSection title={sectionTitle("输出挂载", "Output Mounts")}>
          <div className="space-y-3">
            {derivingSchema ? (
              <div className="rounded-[18px] border border-sky-300/45 bg-sky-500/8 px-3 py-3 text-xs leading-5 text-muted-foreground">
                {copy.deriving}
              </div>
            ) : null}

            {outputGroups.length > 0 ? (
              outputGroups.map((group, index) => (
                <details
                  key={group.key}
                  className="group overflow-hidden rounded-[18px] border border-border/60 bg-background/80"
                  open
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-foreground">
                          {lang === "zh" ? `输出口 ${index + 1}` : `Output ${index + 1}`}
                        </span>
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
                  </summary>
                  <div className="border-t border-border/60 px-4 py-3">
                    <div className="space-y-3">
                      <div className="rounded-[14px] border border-border/60 bg-background/90 px-3 py-3">
                        <div className="text-sm font-medium text-foreground">
                          {lang === "zh" ? "输出" : "Output"}
                        </div>
                        {group.outputFields.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {group.outputFields.map((field) => (
                              <Badge key={`${group.key}:${field}`} variant="outline">
                                {friendlyFieldLabel(field, lang)}
                              </Badge>
                            ))}
                          </div>
                        ) : contractContext.output_contract.field_keys.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {contractContext.output_contract.field_keys.map((field) => (
                              <Badge key={`${group.key}:fallback:${field}`} variant="outline">
                                {friendlyFieldLabel(field, lang)}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <div className="mt-3 text-sm text-muted-foreground">
                            {sectionHint(
                              "这个输出口暂时还没有被下游写死字段，主要由任务说明和运行时推导决定。",
                              "This output port does not have pinned fields yet and is still guided by instructions and runtime derivation.",
                            )}
                          </div>
                        )}
                      </div>
                      {group.consumers.map((consumer) => (
                        <div
                          key={`${consumer.target_port.id}:${consumer.target.node_label}`}
                          className="rounded-[14px] border border-border/60 bg-background/90 px-3 py-3"
                        >
                          <div className="text-sm font-medium text-foreground">
                            {lang === "zh" ? "接收节点" : "Receiving Node"}
                          </div>
                          <div className="mt-3 inline-flex items-center rounded-[14px] border border-border/60 bg-background/95 px-3 py-2 text-sm font-medium text-foreground">
                            {localizeDownstreamLabel(consumer)}
                          </div>
                          <div className="mt-3 text-sm text-muted-foreground">
                            {consumer.required_fields.length > 0
                              ? localizeRequirement(consumer)
                              : localizeDownstreamPurpose(consumer)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              ))
            ) : (
              <div className="rounded-[18px] border border-dashed border-border/60 bg-background/70 px-3 py-3 text-sm leading-6 text-muted-foreground">
                {sectionHint(
                  "当前还没有下游节点接在这个 AI 后面，所以输出契约暂时主要来自你写的任务说明或默认推导。",
                  "No downstream node is connected after this AI yet, so the output contract currently comes mostly from your instructions or fallback derivation.",
                )}
              </div>
            )}
          </div>
        </CollapsibleSection>
      </div>

      {selectedNodeAdvancedFields.length > 0 ? (
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
