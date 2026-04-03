import type { Lang } from "@/i18n";
import type { AgentWorkflowCatalog } from "@/pages/automation/api";
import { friendlyFieldLabel, type UpstreamPortOption } from "./workflow-editor-types";

export interface FrontendAiContractContext {
  upstream_inputs: Array<{
    kind: "data" | "trigger" | "control";
    slot: string;
    label: string;
    source: {
      node_label: string;
      node_type: string;
    };
    from_port: {
      id: string;
      label: string;
    };
    source_summary: string;
    provided_fields: string[];
    usage_note: string;
    slot_note: string;
    note: {
      title: string;
      summary: string;
      operator_note: string;
    };
  }>;
  downstream_consumers: Array<{
    target: {
      node_label: string;
      node_type: string;
    };
    target_port: {
      id: string;
      label: string;
    };
    required_fields: string[];
    usage_note: string;
    requirement_note: string;
    note: {
      title: string;
      summary: string;
      requirement: string;
    };
  }>;
  mounted_tools: Array<{
    key: string;
    label: string;
    description: string;
    allowed_arguments: string[];
    usage_notes: string[];
    note: {
      title: string;
      summary: string;
      tips: string[];
    };
  }>;
  tool_usage_policy: {
    mode: string;
    minimum_tool_calls: number;
  };
  output_contract: {
    summary: string;
    field_keys: string[];
    field_labels: string[];
    has_downstream_consumers: boolean;
  };
}

type ConnectedAiInputSlotBinding = {
  portId: string;
  sourceNode: { data: { label: string; nodeType: string } } | null;
  sourcePort?: { data_schema?: Record<string, unknown> | null } | null;
  note: string;
  humanDescription: string;
  inputSummary: string;
};

type MountedToolSurfaceItem = {
  surfaceKey: string;
  surface?: {
    key?: string;
    label?: string;
    description?: string;
    allowed_args?: string[];
    human_card?: Record<string, string[]>;
  };
};

type AiOutputBindingGroup = {
  portId: string;
  portLabel: string;
  bindings: UpstreamPortOption[];
};

function labelFields(
  fields: [string, Record<string, unknown>][],
  lang: Lang,
) {
  return fields.map(([fieldName, fieldSchema]) =>
    friendlyFieldLabel(fieldName, lang, fieldSchema),
  );
}

export function buildFrontendAiContractContext({
  lang,
  catalog: _catalog,
  connectedAiInputSlotBindings,
  triggerMountSource,
  approvalMountSource,
  mountedToolSurfaces,
  aiOutputBindings,
  describeDownstreamUsage,
  describeDownstreamRequirement,
  derivedOutputSummary,
  derivedOutputFields,
  toolUsageMode,
  minimumToolCalls,
}: {
  lang: Lang;
  catalog: AgentWorkflowCatalog | undefined;
  connectedAiInputSlotBindings: ConnectedAiInputSlotBinding[];
  triggerMountSource: { data: { label: string; nodeType: string } } | null;
  approvalMountSource: { data: { label: string; nodeType: string } } | null;
  mountedToolSurfaces: MountedToolSurfaceItem[];
  aiOutputBindings: AiOutputBindingGroup[];
  describeDownstreamUsage: (option: UpstreamPortOption | null) => string;
  describeDownstreamRequirement: (option: UpstreamPortOption | null) => string;
  derivedOutputSummary: string;
  derivedOutputFields: [string, Record<string, unknown>][];
  toolUsageMode: string;
  minimumToolCalls: number;
}): FrontendAiContractContext {
  const upstream_inputs: FrontendAiContractContext["upstream_inputs"] = [
    ...connectedAiInputSlotBindings.map((slot) => ({
      kind: "data" as const,
      slot: slot.portId,
      label:
        lang === "zh"
          ? `输入口 ${slot.portId.split("_")[1]}`
          : `Input ${slot.portId.split("_")[1]}`,
      source: {
        node_label:
          slot.sourceNode?.data.label || (lang === "zh" ? "未连接" : "Unconnected"),
        node_type: slot.sourceNode?.data.nodeType || "",
      },
      from_port: {
        id: slot.portId,
        label:
          lang === "zh"
            ? `输入口 ${slot.portId.split("_")[1]}`
            : `Input ${slot.portId.split("_")[1]}`,
      },
      source_summary: slot.inputSummary,
      provided_fields: labelFields(
        Object.entries(
          (slot.sourcePort?.data_schema?.properties as Record<string, Record<string, unknown>> | undefined) || {},
        ),
        lang,
      ),
      usage_note: slot.humanDescription,
      slot_note: slot.note,
      note: {
        title:
          lang === "zh"
            ? "AI 会怎样理解这份输入"
            : "How the AI should interpret this input",
        summary: slot.humanDescription,
        operator_note: slot.note,
      },
    })),
    ...(triggerMountSource
      ? [
          {
            kind: "trigger" as const,
            slot: "mount_trigger",
            label: lang === "zh" ? "触发器挂载" : "Trigger Mount",
            source: {
              node_label: triggerMountSource.data.label,
              node_type: triggerMountSource.data.nodeType,
            },
            from_port: {
              id: "mount_trigger",
              label: lang === "zh" ? "触发器挂载" : "Trigger Mount",
            },
            source_summary: "",
            provided_fields: [],
            usage_note:
              lang === "zh"
                ? "这个触发器上下文会告诉 AI 当前是因为什么事件启动的。"
                : "This trigger context tells the AI what event caused the workflow to start.",
            slot_note: "",
            note: {
              title: lang === "zh" ? "触发上下文" : "Trigger Context",
              summary:
                lang === "zh"
                  ? "这一路告诉 AI 当前为什么会运行。"
                  : "This mount tells the AI why it is currently running.",
              operator_note: "",
            },
          },
        ]
      : []),
    ...(approvalMountSource
      ? [
          {
            kind: "control" as const,
            slot: "mount_approval",
            label: lang === "zh" ? "审批挂载" : "Approval Mount",
            source: {
              node_label: approvalMountSource.data.label,
              node_type: approvalMountSource.data.nodeType,
            },
            from_port: {
              id: "mount_approval",
              label: lang === "zh" ? "审批挂载" : "Approval Mount",
            },
            source_summary: "",
            provided_fields: [],
            usage_note:
              lang === "zh"
                ? "这个审批上下文会告诉 AI 人工审批是否已经发生、结果是什么。"
                : "This approval context tells the AI whether human approval already happened and what the decision was.",
            slot_note: "",
            note: {
              title: lang === "zh" ? "审批上下文" : "Approval Context",
              summary:
                lang === "zh"
                  ? "这一路告诉 AI 审批是否已经发生，以及结果是什么。"
                  : "This mount tells the AI whether approval already happened and what the decision was.",
              operator_note: "",
            },
          },
        ]
      : []),
  ];

  const downstream_consumers: FrontendAiContractContext["downstream_consumers"] =
    aiOutputBindings.flatMap(({ portId, portLabel, bindings }) =>
      bindings.map((option) => ({
        target: {
          node_label: option.node_label,
          node_type: option.node_type,
        },
        target_port: {
          id: portId,
          label: portLabel,
        },
        required_fields: labelFields(
          Object.entries(
            (option.data_schema?.properties as Record<string, Record<string, unknown>> | undefined) || {},
          ),
          lang,
        ),
        usage_note: describeDownstreamUsage(option),
        requirement_note: describeDownstreamRequirement(option),
        note: {
          title:
            lang === "zh"
              ? "下游会这样使用你的输出"
              : "Downstream will use your output like this",
          summary: describeDownstreamUsage(option),
          requirement: describeDownstreamRequirement(option),
        },
      })),
    );

  const mounted_tools: FrontendAiContractContext["mounted_tools"] =
    mountedToolSurfaces.map(({ surfaceKey, surface }) => ({
      key: surface?.key || surfaceKey,
      label:
        surface?.label ||
        surfaceKey ||
        (lang === "zh" ? "未选择工具" : "No tool selected"),
      description:
        surface?.description ||
        (lang === "zh"
          ? "这个只读工具还没有说明。"
          : "This readonly tool does not have a description yet."),
      allowed_arguments: surface?.allowed_args || [],
      usage_notes: Object.values(surface?.human_card || {})
        .flat()
        .filter(Boolean)
        .slice(0, 4),
      note: {
        title:
          lang === "zh" ? "这个工具能帮你做什么" : "What this tool can help with",
        summary:
          surface?.description ||
          (lang === "zh"
            ? "这是当前挂给 AI 的只读工具。"
            : "This is a readonly tool mounted on the current AI node."),
        tips: Object.values(surface?.human_card || {})
          .flat()
          .filter(Boolean)
          .slice(0, 4),
      },
    }));

  return {
    upstream_inputs,
    downstream_consumers,
    mounted_tools,
    tool_usage_policy: {
      mode: toolUsageMode,
      minimum_tool_calls: minimumToolCalls,
    },
    output_contract: {
      summary: derivedOutputSummary,
      field_keys: derivedOutputFields.map(([fieldName]) => fieldName),
      field_labels: labelFields(derivedOutputFields, lang),
      has_downstream_consumers: downstream_consumers.length > 0,
    },
  };
}
