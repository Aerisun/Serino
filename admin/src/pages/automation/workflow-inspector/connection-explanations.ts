import type { Lang } from "@/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ConnectionExplanation {
  title: { zh: string; en: string };
  usage: { zh: string; en: string };
  requirement: { zh: string; en: string };
  tip: { zh: string; en: string };
}

export function pickExplanation(exp: ConnectionExplanation, lang: Lang) {
  const pick = (obj: { zh: string; en: string }) => (lang === "zh" ? obj.zh : obj.en);
  return {
    title: pick(exp.title),
    usage: pick(exp.usage),
    requirement: pick(exp.requirement),
    tip: pick(exp.tip),
  };
}

// ---------------------------------------------------------------------------
// Input side: source nodeType → explanation when connecting INTO ai.task
// ---------------------------------------------------------------------------

const INPUT_EXPLANATIONS: Record<string, ConnectionExplanation> = {
  "ai.task": {
    title: {
      zh: "AI 任务输出",
      en: "AI Task Output",
    },
    usage: {
      zh: "上一个 AI 的输出会整体拼进这个 AI 的提示词，作为背景参考。AI 不会逐字复述，而是理解后综合使用。",
      en: "The previous AI task's output is injected into this AI's prompt as background context. The AI will comprehend and use it holistically, not repeat it verbatim.",
    },
    requirement: {
      zh: "通常是自由格式的结构化结果，具体字段取决于上游 AI 的输出约束。",
      en: "Usually a free-form structured result; exact fields depend on the upstream AI's output constraints.",
    },
    tip: {
      zh: "建议在下方备注里写明这份输入的用途，比如「这是上一步的审核意见，仅作参考」。",
      en: "Use the note field below to explain the purpose, e.g. 'This is the previous review opinion, for reference only'.",
    },
  },

  "trigger.event": {
    title: {
      zh: "事件触发上下文",
      en: "Event Trigger Context",
    },
    usage: {
      zh: "平台事件触发时携带的上下文信息，包含事件类型、触发对象类型和 ID。",
      en: "Context carried by a platform event trigger, including event type, target object type and ID.",
    },
    requirement: {
      zh: "通常包含 event_type、target_type、target_id 等元数据字段。",
      en: "Usually contains metadata fields like event_type, target_type, target_id.",
    },
    tip: {
      zh: "事件上下文通常比较精简，如果 AI 需要更多细节，考虑额外挂载只读工具来查询完整信息。",
      en: "Event context is usually concise; if the AI needs more detail, consider mounting a readonly tool to query full info.",
    },
  },

  "trigger.webhook": {
    title: {
      zh: "Webhook 请求体",
      en: "Webhook Request Body",
    },
    usage: {
      zh: "外部系统通过 Webhook 发来的请求数据，格式由调用方决定。",
      en: "Request data sent by an external system via webhook; format is determined by the caller.",
    },
    requirement: {
      zh: "字段结构取决于外部系统的实现，没有固定 schema。",
      en: "Field structure depends on the external system's implementation; no fixed schema.",
    },
    tip: {
      zh: "建议在备注中描述预期的请求格式，帮助 AI 正确解析。",
      en: "Describe the expected request format in the note to help the AI parse correctly.",
    },
  },

  "trigger.manual": {
    title: {
      zh: "手动触发输入",
      en: "Manual Trigger Input",
    },
    usage: {
      zh: "管理员手动触发时传入的参数。",
      en: "Parameters passed when an admin triggers the workflow manually.",
    },
    requirement: {
      zh: "由手动触发时的输入表单决定。",
      en: "Determined by the manual trigger's input form.",
    },
    tip: {
      zh: "手动触发适合调试和一次性任务。",
      en: "Manual triggers are good for debugging and one-off tasks.",
    },
  },

  "trigger.schedule": {
    title: {
      zh: "定时触发上下文",
      en: "Schedule Trigger Context",
    },
    usage: {
      zh: "定时任务触发时的时间戳和调度元数据。",
      en: "Timestamp and scheduling metadata from a scheduled trigger.",
    },
    requirement: {
      zh: "通常只有触发时间等基础字段。",
      en: "Usually only basic fields like trigger timestamp.",
    },
    tip: {
      zh: "定时触发没有业务数据，AI 通常需要配合只读工具自行查询。",
      en: "Scheduled triggers carry no business data; the AI usually needs readonly tools to fetch context.",
    },
  },

  "approval.review": {
    title: {
      zh: "人工审批结果",
      en: "Human Approval Result",
    },
    usage: {
      zh: "人工审核后的决定，包括是否通过、审批原因、审核令牌。",
      en: "Human review decision, including approval status, reason, and approval token.",
    },
    requirement: {
      zh: "包含 decision（action + reason）和 token（granted + auto + approval_type）。",
      en: "Contains decision (action + reason) and token (granted + auto + approval_type).",
    },
    tip: {
      zh: "审批结果中 token.granted 为 true 才代表通过，AI 可据此决定后续逻辑。",
      en: "token.granted must be true for approval; the AI can use this to decide next steps.",
    },
  },

  "flow.condition": {
    title: {
      zh: "条件分支结果",
      en: "Condition Branch Result",
    },
    usage: {
      zh: "条件表达式求值后的布尔结果，表示选择了哪条路径。",
      en: "Boolean result after evaluating the condition expression, indicating which path was taken.",
    },
    requirement: {
      zh: "包含 expression（原始表达式）和 result（true/false）。",
      en: "Contains expression (original) and result (true/false).",
    },
    tip: { zh: "", en: "" },
  },

  "operation.capability": {
    title: {
      zh: "平台操作结果",
      en: "Platform Operation Result",
    },
    usage: {
      zh: "后端平台能力执行后的返回结果，包括操作状态和实际返回数据。",
      en: "Result returned after executing a backend platform capability, including operation status and actual return data.",
    },
    requirement: {
      zh: "包含 status、applied、execution（含 operation_key、arguments、result）。",
      en: "Contains status, applied, execution (with operation_key, arguments, result).",
    },
    tip: { zh: "", en: "" },
  },

  "apply.action": {
    title: {
      zh: "动作执行结果",
      en: "Action Execution Result",
    },
    usage: {
      zh: "动作 Surface 执行后的返回结果。",
      en: "Result returned after executing an action surface.",
    },
    requirement: {
      zh: "包含 status、applied、surface_key、result。",
      en: "Contains status, applied, surface_key, result.",
    },
    tip: { zh: "", en: "" },
  },

  __default__: {
    title: {
      zh: "上游节点输出",
      en: "Upstream Node Output",
    },
    usage: {
      zh: "来自上游节点的结构化输出数据。",
      en: "Structured output data from the upstream node.",
    },
    requirement: {
      zh: "具体字段取决于上游节点类型和配置。",
      en: "Exact fields depend on the upstream node type and configuration.",
    },
    tip: {
      zh: "在备注中描述这份数据的用途，帮助 AI 正确理解。",
      en: "Describe the purpose of this data in the note to help the AI understand correctly.",
    },
  },
};

// ---------------------------------------------------------------------------
// Output side: target nodeType → explanation when connecting FROM ai.task
// ---------------------------------------------------------------------------

const OUTPUT_EXPLANATIONS: Record<string, ConnectionExplanation> = {
  "ai.task": {
    title: {
      zh: "传递给下一个 AI",
      en: "Pass to Next AI",
    },
    usage: {
      zh: "下一个 AI 会把这份输出直接拼进自己的提示词，作为输入背景。不需要严格格式，重点是内容表述清晰。",
      en: "The next AI task injects this result into its own prompt as context. No strict format needed — clarity is key.",
    },
    requirement: {
      zh: "自由格式，无强制字段要求。",
      en: "Free-form, no mandatory field requirements.",
    },
    tip: {
      zh: "如果下游 AI 只关心部分信息，可以在 instructions 里说明只输出关键结论。",
      en: "If the downstream AI only needs part of the info, specify in instructions to output only key conclusions.",
    },
  },

  "notification.webhook": {
    title: {
      zh: "Webhook 通知数据",
      en: "Webhook Notification Data",
    },
    usage: {
      zh: "Webhook 会拿到这份结构化输出去填充发送模板。具体使用哪些字段，由 Webhook 节点的模板变量决定。",
      en: "The webhook notification fills its delivery template with this structured output. Which fields are used depends on the webhook node's template variables.",
    },
    requirement: {
      zh: "默认整份结构化结果都可供模板使用；真正用到哪些字段由 Webhook 模板自己决定。",
      en: "The full structured result is available to the template by default; actual fields used are determined by the webhook template.",
    },
    tip: {
      zh: "确保输出中包含模板需要的关键字段，如 title、message、summary 等。",
      en: "Ensure the output includes key fields the template needs, such as title, message, summary, etc.",
    },
  },

  "apply.action": {
    title: {
      zh: "执行动作参数",
      en: "Action Execution Parameters",
    },
    usage: {
      zh: "AI 需要按照这个动作 Surface 要求的格式输出，系统会自动提取参数去调用平台能力。",
      en: "The AI must output in the format required by the action surface; the system auto-extracts parameters to invoke the platform capability.",
    },
    requirement: {
      zh: "优先看动作 Surface 声明的输入字段；如果没声明，默认读取整份结果。",
      en: "Prefer the action surface's declared input fields; otherwise the whole result is read.",
    },
    tip: {
      zh: "连接动作节点后，系统会自动推导 AI 需要输出的 schema。请确保 AI instructions 中提到需要输出这些字段。",
      en: "After connecting an action node, the system auto-derives the required output schema. Ensure AI instructions mention these fields.",
    },
  },

  "operation.capability": {
    title: {
      zh: "平台能力调用参数",
      en: "Platform Capability Parameters",
    },
    usage: {
      zh: "AI 需要提供调用这个平台能力所需的参数。参数映射由操作节点的 argument_mappings 决定。",
      en: "The AI must provide parameters needed to call this platform capability. Parameter mapping is determined by the operation node's argument_mappings.",
    },
    requirement: {
      zh: "由操作节点的参数映射配置决定，可能引用 AI 输出中的特定字段。",
      en: "Determined by the operation node's argument mapping config; may reference specific fields in the AI output.",
    },
    tip: {
      zh: "检查操作节点的参数映射，确保 AI 输出包含被引用的字段名。",
      en: "Check the operation node's argument mappings to ensure AI output includes referenced field names.",
    },
  },

  "approval.review": {
    title: {
      zh: "提交人工审批",
      en: "Submit for Human Review",
    },
    usage: {
      zh: "人工审核员会看到这份输出。建议包含清晰的摘要、建议动作、以及是否需要审批的标记。",
      en: "The human reviewer will see this output. Include a clear summary, suggested action, and whether approval is needed.",
    },
    requirement: {
      zh: "通常需要 summary（摘要）、action（建议动作）、needs_approval（是否需要人工审批）。",
      en: "Usually needs summary, action (suggested action), needs_approval (whether human approval is required).",
    },
    tip: {
      zh: "审核员可能不了解技术细节，summary 应该用日常语言写明事情的来龙去脉。",
      en: "Reviewers may not know technical details; summary should explain the situation in everyday language.",
    },
  },

  "flow.condition": {
    title: {
      zh: "供条件判断的数据",
      en: "Data for Condition Evaluation",
    },
    usage: {
      zh: "条件分支的表达式会读取这份输出中的字段来决定走哪条路径。",
      en: "The condition branch expression reads fields from this output to decide which path to take.",
    },
    requirement: {
      zh: "由条件表达式中实际引用到的字段决定。",
      en: "Determined by fields actually referenced in the condition expression.",
    },
    tip: {
      zh: "确保 AI 输出的字段名和条件表达式中引用的一致。",
      en: "Ensure AI output field names match those referenced in the condition expression.",
    },
  },

  "flow.delay": {
    title: {
      zh: "延时后继续",
      en: "Continue After Delay",
    },
    usage: {
      zh: "延时节点会携带这份输出等待指定时间后再继续执行下游。",
      en: "The delay node carries this output and waits for the specified duration before continuing downstream.",
    },
    requirement: {
      zh: "无额外字段要求。",
      en: "No additional field requirements.",
    },
    tip: { zh: "", en: "" },
  },

  "flow.poll": {
    title: {
      zh: "轮询检测数据",
      en: "Polling Detection Data",
    },
    usage: {
      zh: "轮询节点会结合这份输出反复检查直到满足条件。",
      en: "The polling node repeatedly checks using this output until a condition is met.",
    },
    requirement: {
      zh: "无额外字段要求。",
      en: "No additional field requirements.",
    },
    tip: { zh: "", en: "" },
  },

  "flow.wait_for_event": {
    title: {
      zh: "等待外部事件",
      en: "Wait for External Event",
    },
    usage: {
      zh: "等待事件节点会保留这份输出，直到指定的外部事件发生后才继续。",
      en: "The wait-for-event node holds this output until the specified external event occurs.",
    },
    requirement: {
      zh: "无额外字段要求。",
      en: "No additional field requirements.",
    },
    tip: { zh: "", en: "" },
  },

  __default__: {
    title: {
      zh: "传递给下游",
      en: "Pass Downstream",
    },
    usage: {
      zh: "下游节点会读取这份结构化输出继续处理。",
      en: "The downstream node reads this structured output and continues processing.",
    },
    requirement: {
      zh: "具体字段取决于下游节点类型和配置。",
      en: "Exact fields depend on the downstream node type and configuration.",
    },
    tip: { zh: "", en: "" },
  },
};

// ---------------------------------------------------------------------------
// Lookup helpers
// ---------------------------------------------------------------------------

export function getInputExplanation(sourceNodeType: string): ConnectionExplanation {
  return INPUT_EXPLANATIONS[sourceNodeType] ?? INPUT_EXPLANATIONS.__default__;
}

export function getOutputExplanation(targetNodeType: string): ConnectionExplanation {
  return OUTPUT_EXPLANATIONS[targetNodeType] ?? OUTPUT_EXPLANATIONS.__default__;
}
