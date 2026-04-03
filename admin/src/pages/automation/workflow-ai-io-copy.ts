import type { Lang } from "@/i18n";
import type { AgentWorkflowCatalog } from "@/pages/automation/api";
import {
  friendlyFieldLabel,
  friendlyNodeTypeLabel,
  schemaProperties,
  type UpstreamPortOption,
} from "./workflow-editor-types";

interface DescribeAiInputParams {
  lang: Lang;
  sourceNodeType: string;
  sourceNodeLabel?: string;
  sourceSummary?: string;
  sourceSchema?: Record<string, unknown> | null;
  catalog: AgentWorkflowCatalog | undefined;
}

function ensureSentence(text: string, lang: Lang) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return "";
  if (lang === "zh") {
    return /[。！？]$/.test(trimmed) ? trimmed : `${trimmed}。`;
  }
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

function firstLine(values: string[] | undefined) {
  return Array.isArray(values)
    ? String(values.find((item) => String(item || "").trim()) || "").trim()
    : "";
}

const ACTION_SURFACE_PURPOSE_ZH: Record<string, string> = {
  create_admin_content: "它会新建一条后台内容，比如文章、日记、想法或摘录。",
  update_admin_content: "它会修改一条后台内容，比如正文、状态或可见范围。",
  delete_admin_content: "它会删除一条后台内容。",
  create_post_item: "它会新建一篇文章。",
  update_post_item: "它会修改一篇文章的标题、正文、状态或可见范围。",
  delete_post_item: "它会删除一篇文章。",
  create_diary_item: "它会新建一篇日记。",
  update_diary_item: "它会修改一篇日记的内容、状态或附加信息。",
  delete_diary_item: "它会删除一篇日记。",
  create_thought_item: "它会新建一条想法。",
  update_thought_item: "它会修改一条想法的内容、状态或可见范围。",
  delete_thought_item: "它会删除一条想法。",
  create_excerpt_item: "它会新建一条摘录。",
  update_excerpt_item: "它会修改一条摘录的内容、来源或状态。",
  delete_excerpt_item: "它会删除一条摘录。",
  bulk_delete_admin_content: "它会批量删除多条后台内容。",
  bulk_update_admin_content_status: "它会批量修改内容状态，比如发布、归档或改回草稿。",
  create_admin_content_category: "它会新建一个内容分类。",
  update_admin_content_category: "它会修改一个内容分类。",
  delete_admin_content_category: "它会删除一个内容分类。",
  moderate_comment: "它会根据你的判断去处理评论，比如通过、拒绝或删除。",
  moderate_guestbook_entry: "它会根据你的判断去处理留言，比如通过、拒绝或删除。",
  update_admin_site_profile: "它会修改站点资料和对外显示的基本信息。",
  update_admin_community_config: "它会修改评论区和社区互动相关设置。",
  upload_admin_asset: "它会上传一个后台资源文件。",
  update_admin_asset: "它会修改资源的说明、分类或可见性。",
  delete_admin_asset: "它会删除一个资源文件。",
  bulk_delete_admin_assets: "它会批量删除多个资源文件。",
  create_admin_record: "它会新建一条后台记录，比如友链、社交链接或页面文案。",
  update_admin_record: "它会修改一条后台记录。",
  delete_admin_record: "它会删除一条后台记录。",
  create_friend_item: "它会新建一条友链站点记录。",
  update_friend_item: "它会修改一条友链站点记录。",
  delete_friend_item: "它会删除一条友链站点记录。",
  check_friend_item: "它会立即检查这个友链站点和订阅源现在是否可用。",
  create_social_link_item: "它会新建一条社交链接。",
  update_social_link_item: "它会修改一条社交链接。",
  delete_social_link_item: "它会删除一条社交链接。",
  create_poem_item: "它会新建一条首页展示的诗句。",
  update_poem_item: "它会修改一条首页展示的诗句。",
  delete_poem_item: "它会删除一条首页展示的诗句。",
  create_page_copy_item: "它会新建一条页面文案配置。",
  update_page_copy_item: "它会修改一条页面文案配置。",
  delete_page_copy_item: "它会删除一条页面文案配置。",
  create_page_display_option_item: "它会新建一条页面显示设置。",
  update_page_display_option_item: "它会修改一条页面显示设置。",
  delete_page_display_option_item: "它会删除一条页面显示设置。",
  create_nav_item: "它会新建一个导航项。",
  update_nav_item: "它会修改一个导航项。",
  delete_nav_item: "它会删除一个导航项。",
  reorder_admin_nav_items: "它会调整导航项的顺序。",
  create_resume_basics_item: "它会新建简历页的基础信息。",
  update_resume_basics_item: "它会修改简历页的基础信息。",
  delete_resume_basics_item: "它会删除简历页的基础信息。",
  create_resume_skill_group_item: "它会新建一组简历技能。",
  update_resume_skill_group_item: "它会修改一组简历技能。",
  delete_resume_skill_group_item: "它会删除一组简历技能。",
  create_resume_experience_item: "它会新建一条简历经历。",
  update_resume_experience_item: "它会修改一条简历经历。",
  delete_resume_experience_item: "它会删除一条简历经历。",
  create_friend_feed_source: "它会新建一个友链抓取源。",
  update_friend_feed_source: "它会修改一个友链抓取源。",
  delete_friend_feed_source: "它会删除一个友链抓取源。",
  trigger_feed_crawl: "它会手动发起一次友链抓取。",
  update_subscription_config: "它会修改订阅设置，比如发信方式、模板或开关。",
  test_subscription_config: "它会按当前订阅设置发一封测试邮件，帮你确认能不能正常发送。",
  update_subscription_subscriber: "它会启用或停用某个订阅者。",
  delete_subscription_subscriber: "它会删除一个订阅者。",
  update_visitor_auth_config: "它会修改访客登录和管理员前台身份绑定相关设置。",
  bind_admin_identity_email: "它会把某个管理员邮箱绑定到前台身份。",
  delete_admin_identity_binding: "它会解除管理员和前台身份的绑定。",
  update_admin_profile_item: "它会修改管理员资料。",
  revoke_admin_session_item: "它会让某个管理员会话失效，相当于把对方登出。",
  create_admin_api_key: "它会新建一个 API Key。",
  update_admin_api_key: "它会修改一个 API Key 的权限或备注。",
  delete_admin_api_key: "它会删除一个 API Key。",
  update_mcp_admin_config_item: "它会修改 MCP 对外访问设置。",
  update_proxy_config_item: "它会修改系统出站代理设置。",
  test_proxy_config_item: "它会测试当前代理设置能不能连通外部服务。",
  create_backup_snapshot_item: "它会新建一份系统备份。",
  restore_backup_snapshot_item: "它会把系统恢复到某个备份快照。",
  update_backup_sync_config_item: "它会修改备份同步设置。",
  trigger_backup_sync_item: "它会手动发起一次备份同步。",
  retry_backup_sync_run_item: "它会把失败的备份同步再跑一次。",
  pause_backup_sync_item: "它会暂停备份同步。",
  resume_backup_sync_item: "它会恢复备份同步。",
  restore_backup_commit_item: "它会从某次备份提交恢复数据。",
  restore_config_revision_item: "它会把配置恢复到某个历史版本。",
  update_agent_model_config_item: "它会修改 Agent 使用的模型和推理设置。",
  create_agent_workflow_item: "它会新建一条工作流。",
  update_agent_workflow_item: "它会修改这条工作流的设置或画布内容。",
  delete_agent_workflow_item: "它会删除这条工作流。",
  resolve_workflow_approval_item: "它会提交审批结果，决定工作流是否继续。",
  create_webhook_subscription_item: "它会新建一个通知订阅。",
  test_webhook_subscription_item: "它会给这个通知订阅发一条测试消息。",
  connect_telegram_webhook_item: "它会把 Telegram 通知所需的连接信息配好。",
  update_webhook_subscription_item: "它会修改这个通知订阅的设置。",
  delete_webhook_subscription_item: "它会删除这个通知订阅。",
  retry_webhook_delivery_item: "它会把失败的通知再发送一次。",
  replay_webhook_dead_letter_item: "它会重新处理一条已经进入死信队列的通知。",
};

function describeActionSurfaceSummaryZh(consumer: {
  surface_label?: string;
  target: { node_label: string };
}) {
  const label = String(consumer.surface_label || "").trim();
  if (label) return `这是执行节点，负责“${label}”这件事。`;
  return `这是执行节点，会根据你的输出去做实际操作。`;
}

function describeActionSurfacePurposeZh(consumer: {
  surface_key?: string;
  surface_label?: string;
  surface_description?: string;
  surface_hints?: string[];
}) {
  const surfaceKey = String(consumer.surface_key || "").trim();
  const surfaceLabel = String(consumer.surface_label || "").trim();
  const surfaceDescription = String(consumer.surface_description || "").trim();
  const surfaceHint = firstLine(consumer.surface_hints);
  if (surfaceKey && ACTION_SURFACE_PURPOSE_ZH[surfaceKey]) {
    return ACTION_SURFACE_PURPOSE_ZH[surfaceKey];
  }
  if (surfaceDescription) return ensureSentence(surfaceDescription, "zh");
  if (surfaceHint) return ensureSentence(surfaceHint, "zh");
  if (surfaceLabel) return `它会去完成“${surfaceLabel}”这件事。`;
  return "它会根据你的输出去执行后台动作。";
}

function isExecutionConsumer(nodeType: string) {
  return nodeType === "apply.action" || nodeType === "operation.capability";
}

function joinFieldLabels(
  schema: Record<string, unknown> | null | undefined,
  lang: Lang,
) {
  return schemaProperties(schema || {})
    .map(([fieldName, fieldSchema]) =>
      friendlyFieldLabel(fieldName, lang, fieldSchema),
    )
    .join(lang === "zh" ? "、" : ", ");
}

export function describeAiInputSource({
  lang,
  sourceNodeType,
  sourceNodeLabel,
  sourceSummary: _sourceSummary,
  sourceSchema,
  catalog,
}: DescribeAiInputParams) {
  const sourceFields = joinFieldLabels(sourceSchema, lang);
  const friendlySourceLabel =
    sourceNodeLabel?.trim() ||
    friendlyNodeTypeLabel(sourceNodeType, catalog, lang);

  const humanDescription =
    sourceNodeType === "ai.task"
        ? lang === "zh"
          ? "这里接的是上一个 AI 给出的结果，你可以接着往下处理。"
          : "This slot receives the structured output from a previous AI node and uses it as upstream context."
        : sourceNodeType === "approval.review"
            ? lang === "zh"
              ? "这里接的是人工审批的结果，你可以根据结果决定下一步。"
              : "This slot receives the decision payload from a human approval node so the AI can continue based on that decision."
            : sourceNodeType === "apply.action"
              ? lang === "zh"
                ? "这里接的是执行节点返回的结果，你可以看看有没有成功，再决定下一步。"
                : "This slot receives the execution result from an action node so the AI can summarize, compensate, or decide the next step."
              : sourceNodeType === "notification.webhook"
                ? lang === "zh"
                  ? "这里接的是通知发送结果，你可以据此判断消息有没有发出去。"
                  : "This slot receives the delivery result from a notification node so the AI can reason about whether notification already happened and what to do next."
                : sourceNodeType === "flow.condition"
                  ? lang === "zh"
                    ? "这里接的是条件判断结果，你可以按这个结果继续处理。"
                    : "This slot receives the decision result from a condition node and continues that decision flow inside the AI."
                  : sourceNodeType === "flow.delay"
                    ? lang === "zh"
                      ? "这里接的是等待后恢复的状态，说明流程已经重新继续了。"
                      : "This slot receives the resumed state from a delay node, indicating that the workflow continued after waiting."
                    : sourceNodeType === "flow.poll"
                      ? lang === "zh"
                        ? "这里接的是轮询结果，通常能看到最新状态和是否成功。"
                        : "This slot receives the status payload from a polling node, usually including whether the polling succeeded and what the latest result was."
                      : sourceNodeType === "flow.wait_for_event"
                        ? lang === "zh"
                          ? "这里接的是外部事件到了之后返回的结果，说明现在可以继续往下走了。"
                          : "This slot receives the resumed event payload from a wait-for-event node, indicating that an external event satisfied the continuation condition."
                        : lang === "zh"
                            ? `${friendlySourceLabel} 的结果会交给当前 AI 继续处理。`
                            : `The output from ${friendlySourceLabel} is injected into the current AI task as structured input.`;

  const inputSummary = sourceFields
    ? lang === "zh"
      ? `这一路会带来这些信息：${sourceFields}。`
      : `This input path provides these fields: ${sourceFields}.`
    : sourceNodeType === "ai.task"
      ? lang === "zh"
        ? "这一路会带来上一个 AI 的完整结果。"
        : "This input path provides the full structured output from the previous AI task."
      : lang === "zh"
          ? `这一路会带来 ${friendlySourceLabel} 的完整结果。`
          : `This input path provides the full structured output from ${friendlySourceLabel}.`;

  return {
    humanDescription,
    inputSummary,
  };
}

export function describeAiUpstreamSlotSummary(
  slot: { kind: string; source: { node_type: string } },
  lang: Lang,
) {
  if (lang !== "zh") return "";
  switch (slot.kind) {
    case "trigger":
      return "这里告诉 AI：这次是因为什么触发的。";
    case "control":
      return "这里告诉 AI：人工审批有没有通过。";
    default:
      if (slot.source.node_type === "input.payload") return "这是这次流程最主要的输入。";
      if (slot.source.node_type === "ai.task") return "这是上一个 AI 给出的结果。";
      if (slot.source.node_type === "approval.review") return "这是人工审批返回的结果。";
      if (slot.source.node_type === "apply.action") return "这是执行节点返回的结果。";
      if (slot.source.node_type === "notification.webhook") return "这是通知发送后的结果。";
      if (slot.source.node_type === "flow.condition") return "这是条件判断给出的结果。";
      if (slot.source.node_type === "flow.delay") return "这是等待结束后恢复的状态。";
      if (slot.source.node_type === "flow.poll") return "这是轮询拿到的最新结果。";
      if (slot.source.node_type === "flow.wait_for_event") return "这是等到外部事件后拿到的结果。";
      return "这是上游交给当前 AI 的输入。";
  }
}

export function describeAiTriggerMount(slot: {
  source: { node_label: string; node_type: string };
  source_summary?: string;
}, lang: Lang) {
  if (lang !== "zh") {
    return slot.source_summary?.trim()
      ? `This trigger starts the workflow when ${slot.source_summary.trim()} happens.`
      : `This trigger controls when the workflow starts.`;
  }
  const summary = String(slot.source_summary || "").trim();
  if (slot.source.node_type === "trigger.manual") {
    return "触发条件：只有手动运行或测试时，流程才会启动。";
  }
  if (slot.source.node_type === "trigger.schedule") {
    return summary
      ? `触发条件：流程会按这个定时规则自动运行，${summary}。`
      : "触发条件：流程会按设定周期自动运行。";
  }
  if (slot.source.node_type === "trigger.webhook") {
    return summary
      ? `触发条件：外部请求打到 ${summary} 时，流程会启动。`
      : "触发条件：外部请求打到这个 Webhook 入口时，流程会启动。";
  }
  if (slot.source.node_type === "trigger.event") {
    return summary
      ? `触发条件：收到 ${summary} 事件时，流程会启动。`
      : "触发条件：收到对应后台事件时，流程会启动。";
  }
  return summary
    ? `触发条件：${summary}。`
    : `触发条件：由 ${slot.source.node_label} 决定流程什么时候启动。`;
}

export function describeAiApprovalMount(slot: {
  source: { node_label: string };
}, lang: Lang) {
  if (lang !== "zh") {
    return `This approval gate lets the AI continue only after ${slot.source.node_label} grants approval.`;
  }
  return `这是 ${slot.source.node_label}。只有审批通过后，当前 AI 才会继续往下走。`;
}

export function describeAiExtraMountLabel(
  slot: { kind: string; label: string },
  lang: Lang,
) {
  if (lang === "zh" && /^Mount\s+\d+$/i.test(slot.label)) {
    return slot.label.replace(/^Mount\s+/i, "挂载口 ");
  }
  return slot.label;
}

export function describeAiExtraMountBadge(
  slot: {
    kind: string;
    source: { node_label: string; node_type: string };
    source_summary?: string;
  },
  lang: Lang,
) {
  if (lang !== "zh") return slot.source.node_label;
  const summary = String(slot.source_summary || "").trim();
  if (slot.kind === "trigger") {
    if (slot.source.node_type === "trigger.manual") return "手动运行";
    if (summary) return summary;
    if (slot.source.node_type === "trigger.event") return "事件触发";
    if (slot.source.node_type === "trigger.schedule") return "定时触发";
    if (slot.source.node_type === "trigger.webhook") return "Webhook 触发";
    return "触发条件";
  }
  if (slot.kind === "control") return "审批结果";
  return slot.source.node_label;
}

interface DescribeAiOutputParams {
  option: UpstreamPortOption | null;
  lang: Lang;
}

export function describeAiDownstreamUsage({
  option,
  lang,
}: DescribeAiOutputParams) {
  const nodeType = option?.node_type;
  if (!nodeType) return "";

  if (nodeType === "ai.task") {
    return lang === "zh"
      ? "下一个 AI 会把这里的结构化结果当作自己的输入背景继续处理。"
      : "The next AI task will use this structured result as input context.";
  }
  if (nodeType === "notification.webhook") {
    return lang === "zh"
      ? "Webhook 通知节点会把这里的结果喂给自己的发送模板。"
      : "The webhook notification node will feed this result into its delivery template.";
  }
  if (nodeType === "apply.action") {
    return lang === "zh"
      ? "执行动作节点会从这里读取字段，再去调用平台动作。"
      : "The action node will read fields from here before calling the platform action.";
  }
  if (nodeType === "approval.review") {
    return lang === "zh"
      ? "人工审批节点会把这里的结果当作审核内容。"
      : "The human approval node will treat this result as review content.";
  }
  if (nodeType === "flow.condition") {
    return lang === "zh"
      ? "条件分支节点会读取这里的结果，再决定走哪条路径。"
      : "The condition node will read this result and decide which path to take.";
  }
  if (nodeType === "flow.delay") {
    return lang === "zh"
      ? "延时节点会带着这里的结果稍后继续执行。"
      : "The delay node will carry this result forward after waiting.";
  }
  if (nodeType === "flow.wait_for_event") {
    return lang === "zh"
      ? "等待事件节点会保留这里的结果，直到继续条件满足。"
      : "The wait-for-event node will retain this result until continuation conditions are met.";
  }
  if (nodeType === "flow.poll") {
    return lang === "zh"
      ? "轮询节点会结合这里的结果继续检查状态。"
      : "The polling node will continue checking state with this result.";
  }

  return (
    option?.explanation ||
    (lang === "zh"
      ? "下游节点会读取这里的结构化结果继续处理。"
      : "The downstream node will continue processing this structured result.")
  );
}

export function describeAiDownstreamSummary(
  consumer: { target: { node_type: string; node_label: string }; surface_label?: string },
  lang: Lang,
) {
  if (lang !== "zh") return "";
  switch (consumer.target.node_type) {
    case "apply.action":
    case "operation.capability":
      return describeActionSurfaceSummaryZh(consumer);
    case "notification.webhook":
      return "这是通知节点，会拿你的结果去发消息。";
    case "approval.review":
      return "这是人工审批节点，会把你的结果交给人来判断。";
    case "flow.condition":
      return "这是条件分支节点，会根据你的结果决定走哪条路。";
    case "flow.delay":
      return "这是等待节点，会带着你的结果稍后继续。";
    case "flow.wait_for_event":
      return "这是等事件节点，会先把你的结果保存起来，等条件到了再继续。";
    case "flow.poll":
      return "这是轮询节点，会拿着你的结果继续查状态。";
    case "ai.task":
      return "这是下一个 AI 节点，会接着处理你给出的结果。";
    default:
      return "这个下游节点会继续使用你的结果。";
  }
}

export function describeAiDownstreamLabel(
  consumer: {
    target: { node_label: string; node_type: string };
    surface_label?: string;
  },
  lang: Lang,
) {
  const targetLabel = String(consumer.target.node_label || "").trim();
  const surfaceLabel = String(consumer.surface_label || "").trim();
  if (lang !== "zh") return surfaceLabel || targetLabel;
  switch (consumer.target.node_type) {
    case "apply.action":
    case "operation.capability":
      return `执行动作 · ${surfaceLabel || targetLabel}`;
    case "notification.webhook":
      return `通知节点 · ${targetLabel}`;
    case "approval.review":
      return `人工审批 · ${targetLabel}`;
    case "flow.condition":
      return `条件分支 · ${targetLabel}`;
    case "flow.delay":
      return `延时等待 · ${targetLabel}`;
    case "flow.wait_for_event":
      return `等待事件 · ${targetLabel}`;
    case "flow.poll":
      return `轮询检测 · ${targetLabel}`;
    case "ai.task":
      return `下一个 AI · ${targetLabel}`;
    default:
      return targetLabel;
  }
}

export function describeAiDownstreamPurpose(
  consumer: {
    target: { node_type: string };
    surface_description?: string;
    surface_hints?: string[];
    format_requirements?: string;
  },
  lang: Lang,
) {
  const surfaceDescription = String(consumer.surface_description || "").trim();
  const formatRequirements = String(consumer.format_requirements || "").trim();
  if (lang !== "zh") {
    if (isExecutionConsumer(consumer.target.node_type) && surfaceDescription) {
      return surfaceDescription;
    }
    switch (consumer.target.node_type) {
      case "apply.action":
      case "operation.capability":
        return "This node will take the AI output as action input and execute it.";
      case "notification.webhook":
        return "This node will use the AI output to send a notification.";
      case "approval.review":
        return "This node will use the AI output as review content.";
      case "flow.condition":
        return "This node will branch based on the AI output.";
      case "flow.delay":
        return "This node will continue later with the AI output.";
      case "flow.wait_for_event":
        return "This node will hold the AI output until the next event arrives.";
      case "flow.poll":
        return "This node will continue polling with the AI output.";
      case "ai.task":
        return "This node will feed the AI output into the next AI task.";
      default:
        return "This downstream node will continue using the AI output.";
    }
  }
  switch (consumer.target.node_type) {
    case "apply.action":
    case "operation.capability":
      return describeActionSurfacePurposeZh(consumer);
    case "approval.review":
      return "它会把这些结果展示给人工审批，交给人来决定要不要继续。";
    case "notification.webhook":
      return formatRequirements
        ? `它会把这些结果拿去发通知，并尽量满足这条格式要求：${formatRequirements}`
        : "它会把这些结果拿去发通知。";
    case "ai.task":
      return "它会把这些结果交给下一个 AI，继续往下做。";
    case "flow.condition":
      return "它会根据这些结果来判断接下来走哪条路。";
    case "flow.delay":
      return "它会先把这些结果带着，等一会儿再继续。";
    case "flow.wait_for_event":
      return "它会先把这些结果存着，等外部条件满足后再继续。";
    case "flow.poll":
      return "它会拿着这些结果继续去查状态。";
    default:
      return "它会继续使用这些结果。";
  }
}

export function describeAiDownstreamRequirementText(
  consumer: { required_fields: string[]; format_requirements?: string; target?: { node_type: string } },
  lang: Lang,
) {
  if (lang !== "zh") return "";
  if (consumer.required_fields.length > 0) {
    const requiredText = `下游明确需要：${consumer.required_fields
      .map((field) => friendlyFieldLabel(field, lang))
      .join("、")}。`;
    if (consumer.target?.node_type === "notification.webhook" && String(consumer.format_requirements || "").trim()) {
      return `${requiredText} 通知格式要求：${String(consumer.format_requirements || "").trim()}。`;
    }
    return requiredText;
  }
  if (consumer.target?.node_type === "notification.webhook" && String(consumer.format_requirements || "").trim()) {
    return `通知格式要求：${String(consumer.format_requirements || "").trim()}。`;
  }
  return "下游会继续使用这份结果，但没有额外写死字段。";
}

export function describeAiDownstreamRequirement({
  option,
  lang,
}: DescribeAiOutputParams) {
  const nodeType = option?.node_type;
  if (!nodeType) return "";

  const suggestedFields = schemaProperties(option?.data_schema || {});
  if (suggestedFields.length > 0) {
    const labels = suggestedFields
      .map(([fieldName, fieldSchema]) =>
        friendlyFieldLabel(fieldName, lang, fieldSchema),
      )
      .join(lang === "zh" ? "、" : ", ");
    return lang === "zh"
      ? `下游已经明确声明需要这些字段：${labels}。`
      : `Downstream explicitly requires these fields: ${labels}.`;
  }

  if (nodeType === "apply.action") {
    return lang === "zh"
      ? "如果动作 surface 没有单独声明输入 schema，就默认读取这里的整份结构化结果。"
      : "If the action surface does not declare a dedicated input schema, it will read the whole structured result from here.";
  }
  if (nodeType === "notification.webhook") {
    return lang === "zh"
      ? "如果通知模板没有限定字段，就默认把这里的整份结构化结果暴露给模板。"
      : "If the notification template does not restrict fields, the full structured result will be available to the template.";
  }
  if (nodeType === "approval.review") {
    return lang === "zh"
      ? "通常至少要有总结、下一步动作、以及是否需要人工确认这类字段。"
      : "In practice this usually needs summary-like fields, next action, and whether approval is required.";
  }
  if (nodeType === "flow.condition") {
    return lang === "zh"
      ? "真正会用到哪些字段，由条件表达式里引用到的字段决定。"
      : "The actual required fields are determined by the fields referenced inside the condition expression.";
  }

  return lang === "zh"
    ? "这个下游默认会读取这里的整份结构化结果，没有额外强制字段。"
    : "This downstream node reads the whole structured result by default without additional mandatory fields.";
}

export function describeAiToolSummary(
  tool: { description: string; note: { summary: string } },
  lang: Lang,
) {
  if (lang !== "zh") return tool.note.summary;
  return tool.description || "这是挂给 AI 的只读工具。";
}
