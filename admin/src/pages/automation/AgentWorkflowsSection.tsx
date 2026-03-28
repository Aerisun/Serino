import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useGetRunsApiV1AdminAutomationRunsGet } from "@serino/api-client/admin";
import { AdminSurface } from "@/components/AdminSurface";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Textarea } from "@/components/ui/Textarea";
import {
  type AgentWorkflowDraft,
  type AgentWorkflowDraftQuestion,
  clearAgentWorkflowDraft,
  createAgentWorkflowFromDraft,
  createAgentWorkflow,
  deleteAgentWorkflow,
  getAgentWorkflowDraft,
  getAgentWorkflows,
  type AgentWorkflow,
  sendAgentWorkflowDraftMessage,
  streamAgentWorkflowDraftMessage,
  updateAgentWorkflow,
} from "@/api/endpoints/agent";
import { useI18n } from "@/i18n";
import { Check, ChevronLeft, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";

const WORKFLOWS_QUERY_KEY = ["admin", "agent", "workflows"] as const;
const WORKFLOW_DRAFT_QUERY_KEY = ["admin", "agent", "workflow-draft"] as const;
const EMPTY_DRAFT_QUESTIONS: AgentWorkflowDraftQuestion[] = [];
const EMPTY_DRAFT_OPTIONS: AgentWorkflowDraftQuestion["options"] = [];

interface DraftSnapshot {
  draft: AgentWorkflowDraft;
}

const mutedActionButtonClassName =
  "bg-slate-100 text-slate-900 border-slate-200 shadow-none backdrop-blur-0 ring-0 hover:bg-slate-200 hover:text-slate-950 dark:bg-slate-800/80 dark:text-slate-100 dark:border-slate-700 dark:hover:bg-slate-800";

const successActionButtonClassName =
  "bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700 hover:text-white dark:bg-emerald-500 dark:text-white dark:hover:bg-emerald-400";

const COPY = {
  zh: {
    title: "Agent 工作流",
    description: "用对话方式把需求说清楚，AI 会先收敛计划，再自动建立工作流。",
    add: "创建工作流",
    edit: "编辑工作流",
    enabled: "已启用",
    disabled: "已停用",
    approval: "人工审批",
    auto: "自动结束",
    trigger: "触发事件",
    runs: "最近运行",
    empty: "还没有工作流，先新增一个。",
    loading: "加载中...",
    createTitle: "新增工作流",
    editTitle: "编辑工作流",
    aiTitle: "创建工作流",
    chatPlaceholder: "例如：当收到评论和留言时自动审核，宽松一点，只拦截辱骂、反党反社会、骚扰和明显垃圾内容，其余直接通过。",
    send: "发送",
    thinking: "AI 正在分析中...",
    structuredInputPlaceholder: "输入自定义答案或补充约束",
    shortcutHint: "↑/↓ 切换，数字键直选，Ctrl / Cmd + Enter 提交",
    freeformLabel: "需求补充",
    nextQuestion: "下一问",
    submitAnswer: "提交",
    backStep: "返回上一问",
    startCreate: "开始创建",
    flowLabel: "",
    flowTitle: "创建流程",
    flowDescription: "第一个 AI 负责把需求收敛成结构化计划，确认触发条件、决策规则、执行步骤和 API/能力调用顺序；第二个 AI 再根据这份计划生成最终工作流配置。",
    flowUsageTitle: "当前流程",
    flowUsageItems: [
      "先通过问卷式对话收敛需求，优先一次确认多个关键决策。",
      "计划文档会详细列出 step_id、action、capability、expected_result 和 fallback。",
      "计划完成后，再由执行 AI 生成最终工作流定义。",
    ],
    planAction: "查看计划",
    clearDraftConfirmTitle: "确认清空当前草稿？",
    clearDraftConfirmDescription: "这会删除当前对话和计划内容，无法恢复。",
    clearDraftConfirmLabel: "清空草稿",
    createConfirmTitle: "确认开始创建工作流？",
    createConfirmDescription: "系统会把当前已收敛的计划交给执行 AI 在后台生成最终工作流配置。",
    createEarlyConfirmTitle: "计划尚未完成，仍然直接创建？",
    createEarlyConfirmDescription: "建议先完成当前问卷和计划收敛；如果继续，系统会在后台基于当前信息直接尝试生成工作流。",
    createConfirmLabel: "开始创建",
    createBackgroundStarted: "已开始在后台创建工作流",
    createBackgroundHint: "你可以关闭当前弹窗，创建完成后会在页面右上角通知你。",
    creating: "正在创建...",
    createNow: "直接创建",
    clearDraft: "清空草稿",
    noDraft: "还没有草稿，先告诉 AI 你想要什么工作流。",
    draftReady: "已可创建",
    draftActive: "继续澄清中",
    draftFinalizing: "已收敛，正在补全文档",
    viewPlan: "查看计划",
    closePlan: "关闭",
    workingDocument: "临时工作文档",
    draftSummary: "当前总结",
    customOption: "其他补充",
    key: "工作流 Key",
    name: "名称",
    triggerPlaceholder: "comment.pending",
    save: "保存",
    saving: "保存中...",
    deleteConfirm: "确定删除这个工作流吗？",
    enabledHint: "关闭后不会再响应事件。",
    approvalHint: "自动结束会直接产出结果，不再进入人工审批。",
  },
  en: {
    title: "Agent Workflows",
    description: "Describe the requirement in conversation. AI will clarify the plan first, then create the workflow for you.",
    add: "Create Workflow",
    edit: "Edit workflow",
    enabled: "Enabled",
    disabled: "Disabled",
    approval: "Human approval",
    auto: "Auto-complete",
    trigger: "Trigger",
    runs: "Recent runs",
    empty: "No workflows yet.",
    loading: "Loading...",
    createTitle: "Add workflow",
    editTitle: "Edit workflow",
    aiTitle: "Create Workflow",
    chatPlaceholder: "Example: when comments or guestbook messages arrive, review them automatically with a lenient policy and approve everything except abuse, extremist content, harassment, or obvious spam.",
    send: "Send",
    thinking: "AI is thinking...",
    structuredInputPlaceholder: "Enter the custom answer or extra constraint",
    shortcutHint: "Use ↑/↓ to move, number keys to choose, Ctrl / Cmd + Enter to submit",
    freeformLabel: "Requirement",
    nextQuestion: "Next",
    submitAnswer: "Submit",
    backStep: "Go back",
    startCreate: "Start Create",
    flowLabel: "",
    flowTitle: "Creation Flow",
    flowDescription: "The first AI narrows the requirement into a structured plan with trigger rules, decision paths, execution steps, and API or capability calls. The second AI then turns that plan into the final workflow config.",
    flowUsageTitle: "Current Flow",
    flowUsageItems: [
      "Use questionnaire-style follow-up rounds to collect multiple missing decisions together.",
      "The plan document should spell out step_id, action, capability, expected_result, and fallback.",
      "Only after the plan is solid should the execution AI generate the final workflow.",
    ],
    planAction: "View Plan",
    clearDraftConfirmTitle: "Clear the current draft?",
    clearDraftConfirmDescription: "This will remove the current conversation and plan, and cannot be undone.",
    clearDraftConfirmLabel: "Clear Draft",
    createConfirmTitle: "Start creating the workflow now?",
    createConfirmDescription: "The current plan will be handed to the execution AI to generate the final workflow config in the background.",
    createEarlyConfirmTitle: "The plan is not finished yet. Create anyway?",
    createEarlyConfirmDescription: "It is safer to finish the questionnaire first. If you continue, the workflow will be generated in the background from the current partial plan.",
    createConfirmLabel: "Start Create",
    createBackgroundStarted: "Background workflow creation started",
    createBackgroundHint: "You can close this dialog now. A toast will appear in the top-right when creation finishes.",
    creating: "Creating...",
    createNow: "Create now",
    clearDraft: "Clear draft",
    noDraft: "No draft yet. Tell the AI what workflow you want first.",
    draftReady: "Ready to create",
    draftActive: "Clarifying",
    draftFinalizing: "Clarified, finishing the plan",
    viewPlan: "View plan",
    closePlan: "Close",
    workingDocument: "Temporary working document",
    draftSummary: "Current summary",
    customOption: "Other",
    key: "Workflow key",
    name: "Name",
    triggerPlaceholder: "comment.pending",
    save: "Save",
    saving: "Saving...",
    deleteConfirm: "Delete this workflow?",
    enabledHint: "Disabled workflows will stop reacting to events.",
    approvalHint: "Auto-complete skips the manual approval step.",
  },
} as const;

function emptyForm() {
  return {
    key: "",
    name: "",
    description: "",
    trigger_event: "",
    target_type: "",
    enabled: true,
    require_human_approval: true,
    instructions: "",
  };
}

function toForm(workflow: AgentWorkflow) {
  return {
    key: workflow.key,
    name: workflow.name,
    description: workflow.description,
    trigger_event: workflow.trigger_event,
    target_type: workflow.target_type || "",
    enabled: workflow.enabled,
    require_human_approval: workflow.require_human_approval,
    instructions: workflow.instructions,
  };
}

export function AgentWorkflowsSection() {
  const { lang } = useI18n();
  const copy = COPY[lang];
  const queryClient = useQueryClient();
  const { data: workflows, isLoading } = useQuery({
    queryKey: WORKFLOWS_QUERY_KEY,
    queryFn: getAgentWorkflows,
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [confirmCreateOpen, setConfirmCreateOpen] = useState(false);
  const { data: runsRaw } = useGetRunsApiV1AdminAutomationRunsGet();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [form, setForm] = useState(() => emptyForm());
  const [chatInput, setChatInput] = useState("");
  const [draftState, setDraftState] = useState<AgentWorkflowDraft | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [streamingStatus, setStreamingStatus] = useState("");
  const [streamingElapsedSeconds, setStreamingElapsedSeconds] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);
  const [hideStructuredComposer, setHideStructuredComposer] = useState(false);
  const [isRestoringStep, setIsRestoringStep] = useState(false);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [activeOptionIndex, setActiveOptionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [customAnswerInputs, setCustomAnswerInputs] = useState<Record<string, string>>({});
  const [draftSnapshots, setDraftSnapshots] = useState<DraftSnapshot[]>([]);
  const chatViewportRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const structuredPanelRef = useRef<HTMLDivElement | null>(null);
  const { data: workflowDraft, isLoading: isDraftLoading } = useQuery({
    queryKey: WORKFLOW_DRAFT_QUERY_KEY,
    queryFn: getAgentWorkflowDraft,
    enabled: createOpen,
    refetchInterval: (query) =>
      createOpen && query.state.data?.status === "finalizing_plan" ? 1500 : false,
  });

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        trigger_event: form.trigger_event.trim(),
        target_type: form.target_type.trim() || null,
        enabled: form.enabled,
        require_human_approval: form.require_human_approval,
        instructions: form.instructions.trim(),
      };
      if (editingKey) {
        return updateAgentWorkflow(editingKey, payload);
      }
      return createAgentWorkflow({
        ...payload,
        key: form.key.trim(),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
      setEditOpen(false);
      setEditingKey(null);
      setForm(emptyForm());
      toast.success(lang === "zh" ? "工作流已保存" : "Workflow saved");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const createFromDraft = useMutation({
    mutationFn: (force: boolean) => createAgentWorkflowFromDraft(force),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
      await queryClient.invalidateQueries({ queryKey: WORKFLOW_DRAFT_QUERY_KEY });
      setCreateOpen(false);
      setPlanOpen(false);
      setChatInput("");
      setDraftState(null);
      setStreamingText("");
      setStreamingStatus("");
      setStreamingElapsedSeconds(0);
      setIsStreaming(false);
      setHideStructuredComposer(false);
      setIsRestoringStep(false);
      setCurrentQuestionIndex(0);
      setSelectedAnswers({});
      setCustomAnswerInputs({});
      setDraftSnapshots([]);
      toast.success(result.summary);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const clearDraft = useMutation({
    mutationFn: clearAgentWorkflowDraft,
    onSuccess: async () => {
      setChatInput("");
      await queryClient.invalidateQueries({ queryKey: WORKFLOW_DRAFT_QUERY_KEY });
      setDraftState(null);
      setStreamingText("");
      setStreamingStatus("");
      setStreamingElapsedSeconds(0);
      setIsStreaming(false);
      setHideStructuredComposer(false);
      setIsRestoringStep(false);
      setCurrentQuestionIndex(0);
      setSelectedAnswers({});
      setCustomAnswerInputs({});
      setDraftSnapshots([]);
      toast.success(lang === "zh" ? "草稿已清空" : "Draft cleared");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const remove = useMutation({
    mutationFn: deleteAgentWorkflow,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
      toast.success(lang === "zh" ? "工作流已删除" : "Workflow deleted");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  useEffect(() => {
    if (!editOpen) {
      setEditingKey(null);
      setForm(emptyForm());
    }
  }, [editOpen]);

  useEffect(() => {
    if (workflowDraft) {
      setDraftState(workflowDraft);
    } else if (!isDraftLoading && !isStreaming) {
      setDraftState(null);
    }
  }, [workflowDraft, isDraftLoading, isStreaming]);

  useEffect(() => {
    if (!createOpen) {
      setPlanOpen(false);
      setConfirmClearOpen(false);
      setConfirmCreateOpen(false);
      setStreamingText("");
      setStreamingStatus("");
      setStreamingElapsedSeconds(0);
      setIsStreaming(false);
      setHideStructuredComposer(false);
      setIsRestoringStep(false);
      setCurrentQuestionIndex(0);
      setActiveOptionIndex(0);
      setSelectedAnswers({});
      setCustomAnswerInputs({});
      setDraftSnapshots([]);
    }
  }, [createOpen]);

  useEffect(() => {
    if (!chatViewportRef.current) return;
    chatViewportRef.current.scrollTop = chatViewportRef.current.scrollHeight;
  }, [draftState, streamingText, isStreaming]);

  const runCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const run of runsRaw?.data ?? []) {
      counts.set(run.workflow_key, (counts.get(run.workflow_key) ?? 0) + 1);
    }
    return counts;
  }, [runsRaw?.data]);

  const items = workflows ?? [];
  const activeDraft = draftState ?? workflowDraft ?? null;
  const displayedMessages = activeDraft?.messages ?? [];
  const compatibilityOptions = activeDraft?.options ?? EMPTY_DRAFT_OPTIONS;
  const activeQuestions = useMemo(() => {
    if (activeDraft?.questions?.length) {
      return activeDraft.questions;
    }
    if (activeDraft?.current_question && compatibilityOptions.length) {
      return [
        {
          key: "q1",
          prompt: activeDraft.current_question,
          options: compatibilityOptions,
        },
      ];
    }
    return EMPTY_DRAFT_QUESTIONS;
  }, [activeDraft, compatibilityOptions]);
  const currentQuestion = activeQuestions[currentQuestionIndex] ?? null;
  const activeOptions = currentQuestion?.options ?? EMPTY_DRAFT_OPTIONS;
  const selectedOptionValue = currentQuestion ? selectedAnswers[currentQuestion.key] ?? null : null;
  const selectedOption = activeOptions.find((option) => option.value === selectedOptionValue) ?? null;
  const currentCustomInput = currentQuestion ? customAnswerInputs[currentQuestion.key] ?? "" : "";
  const optionRequiresInput = Boolean(
    selectedOption &&
      (selectedOption.requires_input || selectedOption.value.trim().toLowerCase() === "other")
  );
  const hasStructuredComposer = Boolean(currentQuestion);
  const showStructuredComposer = hasStructuredComposer && !hideStructuredComposer && !isStreaming;
  const hasPreviousStructuredStep = draftSnapshots.length > 0;
  const isLastStructuredQuestion = currentQuestionIndex >= activeQuestions.length - 1;
  const structuredSubmitLabel = isLastStructuredQuestion ? copy.submitAnswer : copy.nextQuestion;
  const currentQuestionReady = Boolean(
    currentQuestion &&
      selectedOption &&
      (!optionRequiresInput || currentCustomInput.trim())
  );
  const pendingMessage = useMemo(() => {
    if (showStructuredComposer) {
      const lines: string[] = [];
      for (const [index, question] of activeQuestions.entries()) {
        const optionValue = selectedAnswers[question.key];
        const option = question.options.find((item) => item.value === optionValue);
        if (!option) {
          return "";
        }
        const customInput = (customAnswerInputs[question.key] ?? "").trim();
        const needsInput = Boolean(
          option.requires_input || option.value.trim().toLowerCase() === "other"
        );
        if (needsInput && !customInput) {
          return "";
        }
        lines.push(`${index + 1}. ${question.prompt}`);
        lines.push(`选择: ${option.value}`);
        if (needsInput) {
          lines.push(`补充: ${customInput}`);
        }
      }
      return lines.join("\n");
    }
    return chatInput.trim();
  }, [activeQuestions, chatInput, customAnswerInputs, selectedAnswers, showStructuredComposer]);
  const canAttemptCreate = Boolean(activeDraft || pendingMessage);
  const createActionReady = Boolean(activeDraft?.ready_to_create);
  const createActionLabel = createActionReady ? copy.startCreate : copy.createNow;
  const createActionClassName = createActionReady ? successActionButtonClassName : mutedActionButtonClassName;
  const streamingStatusLabel = useMemo(() => {
    switch (streamingStatus) {
      case "collecting_context":
      case "loading_draft":
        return lang === "zh" ? "正在读取当前草稿和历史对话" : "Loading the current draft and conversation";
      case "matching_template":
      case "building_execution_context":
        return lang === "zh" ? "正在收集模板、API 和能力上下文" : "Collecting templates, APIs, and capability context";
      case "planning_questionnaire":
      case "invoking_planner_model":
        return lang === "zh" ? "正在调用规划模型" : "Calling the planning model";
      case "waiting_for_model":
        return lang === "zh"
          ? `正在等待模型返回，已等待 ${streamingElapsedSeconds} 秒`
          : `Waiting for the model response, ${streamingElapsedSeconds}s elapsed`;
      case "drafting_working_document":
      case "processing_model_output":
        return lang === "zh" ? "正在处理模型输出并组织问题" : "Processing the model output and structuring questions";
      case "finalizing_response":
      case "saving_draft":
        return lang === "zh" ? "正在保存草稿和计划" : "Saving the draft and plan";
      default:
        return streamingStatus
          ? streamingStatus.replaceAll("_", " ")
          : "";
    }
  }, [lang, streamingElapsedSeconds, streamingStatus]);

  useEffect(() => {
    if (!showStructuredComposer || optionRequiresInput) return;
    const raf = requestAnimationFrame(() => structuredPanelRef.current?.focus());
    return () => cancelAnimationFrame(raf);
  }, [optionRequiresInput, showStructuredComposer, activeDraft?.updated_at, currentQuestionIndex]);

  useEffect(() => {
    if (!activeOptions.length) {
      setActiveOptionIndex(0);
      return;
    }
    if (selectedOptionValue) {
      const selectedIndex = activeOptions.findIndex((option) => option.value === selectedOptionValue);
      if (selectedIndex >= 0) {
        setActiveOptionIndex(selectedIndex);
        return;
      }
    }
    setActiveOptionIndex((current) => Math.min(current, activeOptions.length - 1));
  }, [activeOptions, selectedOptionValue]);

  useEffect(() => {
    setCurrentQuestionIndex(0);
    setActiveOptionIndex(0);
    setSelectedAnswers({});
    setCustomAnswerInputs({});
    if (!isStreaming) {
      setHideStructuredComposer(false);
    }
  }, [activeDraft?.updated_at, isStreaming]);

  const handleOptionSelect = (option: { label: string; value: string; requires_input: boolean }) => {
    if (!currentQuestion) return;
    const optionValue = option.value.trim();
    const nextIndex = activeOptions.findIndex((item) => item.value === option.value);
    if (nextIndex >= 0) {
      setActiveOptionIndex(nextIndex);
    }
    setSelectedAnswers((current) => ({ ...current, [currentQuestion.key]: optionValue }));
    setCustomAnswerInputs((current) => {
      const next = { ...current };
      delete next[currentQuestion.key];
      return next;
    });
    if (option.requires_input || optionValue.toLowerCase() === "other") {
      setChatInput("");
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  };

  const sendDraftMessage = async (
    message: string,
    options?: {
      checkpointDraft?: AgentWorkflowDraft | null;
    }
  ) => {
    const content = message.trim();
    if (!content) return false;
    if (options?.checkpointDraft) {
      setDraftSnapshots((current) => [...current, { draft: options.checkpointDraft! }]);
    }
    setIsStreaming(true);
    setHideStructuredComposer(true);
    setStreamingText("");
    setStreamingStatus("loading_draft");
    setStreamingElapsedSeconds(0);
    const now = new Date().toISOString();
    setDraftState((current) => ({
      ...(current ?? {
        id: "global",
        status: "active",
        summary: "",
        ready_to_create: false,
        suggested_template: null,
        questions: [],
        current_question: "",
        options: [],
        working_document: "",
        messages: [],
        created_at: now,
        updated_at: now,
      }),
      status: "active",
      ready_to_create: false,
      questions: [],
      current_question: "",
      options: [],
      updated_at: now,
      messages: [
        ...((current?.messages ?? []).slice(-19)),
        { role: "user", content, created_at: now },
      ],
    }));
    try {
      await streamAgentWorkflowDraftMessage(content, (event) => {
        if (event.type === "status") {
          setIsStreaming(true);
          setStreamingText("");
          setStreamingStatus(event.status);
          setStreamingElapsedSeconds(event.elapsed_seconds ?? 0);
          return;
        }
        if (event.type === "chunk") {
          setStreamingStatus("");
          setStreamingElapsedSeconds(0);
          setStreamingText((current) => current + event.content);
          return;
        }
        if (event.type === "done") {
          setDraftState(event.draft);
          setStreamingText("");
          setStreamingStatus("");
          setStreamingElapsedSeconds(0);
          setIsStreaming(false);
          void queryClient.invalidateQueries({ queryKey: WORKFLOW_DRAFT_QUERY_KEY });
        }
      });
      setChatInput("");
      setCurrentQuestionIndex(0);
      setSelectedAnswers({});
      setCustomAnswerInputs({});
      setHideStructuredComposer(false);
      return true;
    } catch (error: any) {
      setIsStreaming(false);
      setHideStructuredComposer(false);
      setStreamingText("");
      setStreamingStatus("");
      setStreamingElapsedSeconds(0);
      if (options?.checkpointDraft) {
        setDraftSnapshots((current) => current.slice(0, -1));
      }
      toast.error(error?.message || (lang === "zh" ? "对话失败" : "Conversation failed"));
      await queryClient.invalidateQueries({ queryKey: WORKFLOW_DRAFT_QUERY_KEY });
      return false;
    }
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!(event.ctrlKey || event.metaKey) || event.key !== "Enter") return;
    event.preventDefault();
    if (showStructuredComposer) {
      void handleStructuredAdvance();
      return;
    }
    void sendDraftMessage(pendingMessage, {
      checkpointDraft: null,
    });
  };

  const handleStructuredAdvance = async () => {
    if (!showStructuredComposer || !currentQuestionReady) return;
    if (!isLastStructuredQuestion) {
      setCurrentQuestionIndex((current) => Math.min(current + 1, activeQuestions.length - 1));
      return;
    }
    await sendDraftMessage(pendingMessage, {
      checkpointDraft: activeDraft,
    });
  };

  const handleGoBackStep = async () => {
    if (showStructuredComposer && currentQuestionIndex > 0) {
      setCurrentQuestionIndex((current) => Math.max(current - 1, 0));
      return;
    }
    const previousSnapshot = draftSnapshots.at(-1);
    if (!previousSnapshot || isStreaming || createFromDraft.isPending || isRestoringStep) {
      return;
    }

    setIsRestoringStep(true);
    setStreamingText("");
    try {
      await clearAgentWorkflowDraft();
      const userMessages = previousSnapshot.draft.messages.filter((message) => message.role === "user");

      let restoredDraft: AgentWorkflowDraft | null = null;
      for (const message of userMessages) {
        restoredDraft = await sendAgentWorkflowDraftMessage(message.content);
      }

      setDraftState(restoredDraft ?? previousSnapshot.draft);
      setHideStructuredComposer(false);
      setDraftSnapshots((current) => current.slice(0, -1));
      setCurrentQuestionIndex(0);
      setSelectedAnswers({});
      setCustomAnswerInputs({});
      void queryClient.invalidateQueries({ queryKey: WORKFLOW_DRAFT_QUERY_KEY });
    } catch (error: any) {
      toast.error(error?.message || (lang === "zh" ? "返回上一问失败" : "Failed to go back"));
      await queryClient.invalidateQueries({ queryKey: WORKFLOW_DRAFT_QUERY_KEY });
    } finally {
      setIsRestoringStep(false);
    }
  };

  const handleStructuredPanelKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!activeOptions.length || isStreaming || createFromDraft.isPending || isRestoringStep) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveOptionIndex((current) => (current + 1) % activeOptions.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveOptionIndex((current) => (current - 1 + activeOptions.length) % activeOptions.length);
      return;
    }

    if (/^[1-9]$/.test(event.key)) {
      const nextIndex = Number(event.key) - 1;
      if (nextIndex < activeOptions.length) {
        event.preventDefault();
        handleOptionSelect(activeOptions[nextIndex]);
      }
      return;
    }

    if (event.key === "Enter" && !event.ctrlKey && !event.metaKey) {
      const activeOption = activeOptions[activeOptionIndex];
      if (!activeOption) return;
      event.preventDefault();
      if (activeOption.requires_input || activeOption.value.trim().toLowerCase() === "other") {
        handleOptionSelect(activeOption);
        return;
      }
      handleOptionSelect(activeOption);
      void handleStructuredAdvance();
    }
  };

  const handleRequestCreate = () => {
    if (!canAttemptCreate || activeDraft?.status === "finalizing_plan" || isStreaming || createFromDraft.isPending || isRestoringStep) {
      return;
    }
    setConfirmCreateOpen(true);
  };

  const handleConfirmCreate = async () => {
    setConfirmCreateOpen(false);
    setCreateOpen(false);
    setPlanOpen(false);
    toast(copy.createBackgroundStarted, {
      description: copy.createBackgroundHint,
    });
    void handleCreateNow();
  };

  const handleRequestClear = () => {
    if (!activeDraft || clearDraft.isPending || isStreaming || createFromDraft.isPending || isRestoringStep) {
      return;
    }
    setConfirmClearOpen(true);
  };

  const handleConfirmClear = () => {
    setConfirmClearOpen(false);
    clearDraft.mutate();
  };

  const handleCreateNow = async () => {
    if (showStructuredComposer && !pendingMessage) {
      return;
    }
    if (pendingMessage) {
      const sent = await sendDraftMessage(pendingMessage);
      if (!sent) return;
      await createFromDraft.mutateAsync(true);
      return;
    }
    await createFromDraft.mutateAsync(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Sparkles className="mr-2 h-4 w-4" />
              {copy.add}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-5xl">
            <DialogHeader className="flex-row items-center justify-between space-y-0">
              <div className="flex items-center gap-2">
                <DialogTitle>{copy.aiTitle}</DialogTitle>
                <LabelWithHelp
                  label={null}
                  title={copy.flowTitle}
                  description={copy.flowDescription}
                  usageTitle={copy.flowUsageTitle}
                  usageItems={copy.flowUsageItems}
                  className="shrink-0"
                />
              </div>
              <DialogDescription className="sr-only">
                {lang === "zh"
                  ? "通过问卷和计划收敛来创建新的 Agent 工作流。"
                  : "Create a new agent workflow through questionnaire-style clarification and planning."}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="rounded-[var(--admin-radius-xl)] border border-border/60 bg-[linear-gradient(180deg,rgb(var(--admin-surface-1)/0.68),rgb(var(--admin-surface-1)/0.38))] p-3 shadow-[0_22px_50px_-42px_rgba(15,23,42,0.45)]">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={
                        activeDraft?.status === "finalizing_plan"
                          ? "info"
                          : activeDraft?.ready_to_create
                            ? "success"
                            : "warning"
                      }
                    >
                      {activeDraft?.status === "finalizing_plan"
                        ? copy.draftFinalizing
                        : activeDraft?.ready_to_create
                          ? copy.draftReady
                          : copy.draftActive}
                    </Badge>
                    {activeDraft?.suggested_template ? (
                      <Badge variant="outline" className="font-mono">
                        {activeDraft.suggested_template}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      className={mutedActionButtonClassName}
                      onClick={handleRequestClear}
                      disabled={!activeDraft || clearDraft.isPending || isStreaming || createFromDraft.isPending || isRestoringStep}
                    >
                      {copy.clearDraft}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="preview-glow-button"
                      onClick={() => setPlanOpen(true)}
                      disabled={!activeDraft || (!activeDraft.summary && !activeDraft.working_document)}
                    >
                      {copy.planAction}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      className={createActionClassName}
                      onClick={handleRequestCreate}
                      disabled={
                        !canAttemptCreate ||
                        activeDraft?.status === "finalizing_plan" ||
                        isStreaming ||
                        createFromDraft.isPending ||
                        isRestoringStep ||
                        (showStructuredComposer && !pendingMessage)
                      }
                    >
                      {createFromDraft.isPending ? copy.creating : createActionLabel}
                    </Button>
                  </div>
                </div>

                <div
                  ref={chatViewportRef}
                  className="max-h-[26rem] space-y-2 overflow-y-auto rounded-[var(--admin-radius-lg)] border border-border/50 bg-background/55 p-3"
                >
                  {!activeDraft && !isStreaming && !isDraftLoading ? (
                    <p className="text-[13px] text-muted-foreground">{copy.noDraft}</p>
                  ) : null}

                  {displayedMessages.map((message, index) => (
                    <div
                      key={`${message.created_at}-${index}`}
                      className={
                        message.role === "user"
                          ? "ml-auto max-w-[82%] rounded-[1.15rem] border border-[rgb(var(--admin-accent-rgb)/0.25)] bg-[linear-gradient(135deg,rgb(var(--admin-accent-rgb)/0.14),rgb(var(--admin-glow-rgb)/0.08))] px-3 py-2.5 text-[13px] shadow-[0_16px_36px_-28px_rgb(var(--admin-accent-rgb)/0.48)]"
                          : "mr-auto max-w-[88%] rounded-[1.15rem] border border-border/60 bg-background/85 px-3 py-2.5 text-[13px] shadow-[0_16px_36px_-30px_rgba(15,23,42,0.28)]"
                      }
                    >
                      <div className="mb-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                        {message.role === "user" ? "You" : "AI"}
                      </div>
                      <div className="whitespace-pre-wrap leading-5.5 text-foreground">{message.content}</div>
                    </div>
                  ))}

                  {isStreaming ? (
                    <div className="mr-auto max-w-[88%] rounded-[1.15rem] border border-border/60 bg-background/85 px-3 py-2.5 text-[13px] shadow-[0_16px_36px_-30px_rgba(15,23,42,0.28)]">
                      <div className="mb-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                        AI
                      </div>
                      <div className="whitespace-pre-wrap leading-5.5 text-foreground">
                        {streamingText || streamingStatusLabel || copy.thinking}
                      </div>
                    </div>
                  ) : null}
                </div>

                {showStructuredComposer && currentQuestion ? (
                  <div
                    ref={structuredPanelRef}
                    tabIndex={0}
                    onKeyDown={handleStructuredPanelKeyDown}
                    role="listbox"
                    aria-label={currentQuestion.prompt}
                    className="mt-2 overflow-hidden rounded-[0.6rem] border border-border/70 bg-background/95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70"
                  >
                    <div className="border-b border-border/60 bg-[rgb(var(--admin-surface-1)/0.45)] px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[12px] leading-5 text-foreground">{currentQuestion.prompt}</div>
                        {activeQuestions.length > 1 ? (
                          <div className="shrink-0 text-[10px] text-muted-foreground">
                            {currentQuestionIndex + 1}/{activeQuestions.length}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    <div className="space-y-px bg-[rgb(var(--admin-surface-1)/0.18)] px-1.5 py-1.5">
                      {activeOptions.map((option, index) => {
                        const isActive = index === activeOptionIndex;
                        const isSelected = selectedOptionValue === option.value;
                        return (
                          <button
                            key={`${option.label}-${option.value}`}
                            type="button"
                            role="option"
                            aria-selected={isSelected}
                            aria-pressed={isSelected}
                            className={
                              isSelected
                                ? "flex w-full items-start gap-2 rounded-[0.45rem] border border-[rgb(var(--admin-accent-rgb)/0.28)] bg-[rgb(var(--admin-accent-rgb)/0.06)] px-2.5 py-1.5 text-left transition"
                                : isActive
                                  ? "flex w-full items-start gap-2 rounded-[0.45rem] border border-border/70 bg-[rgb(var(--admin-surface-1)/0.9)] px-2.5 py-1.5 text-left transition"
                                  : "flex w-full items-start gap-2 rounded-[0.45rem] border border-transparent bg-background/90 px-2.5 py-1.5 text-left transition hover:border-border/60 hover:bg-[rgb(var(--admin-surface-1)/0.72)]"
                            }
                            disabled={isStreaming || createFromDraft.isPending}
                            onClick={() => {
                              handleOptionSelect(option);
                              structuredPanelRef.current?.focus();
                            }}
                            onMouseEnter={() => setActiveOptionIndex(index)}
                          >
                            <div
                              className={
                                isSelected
                                  ? "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--admin-accent-rgb)/0.18)] text-[10px] font-semibold text-foreground"
                                  : "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border/60 bg-background/70 text-[10px] font-semibold text-muted-foreground"
                              }
                            >
                              {index + 1}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[12px] font-medium leading-5 text-foreground">{option.label}</div>
                              {option.description ? (
                                <div className="truncate text-[11px] leading-4.5 text-muted-foreground">
                                  {option.description}
                                </div>
                              ) : null}
                            </div>
                            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                              <Check
                                className={
                                  isSelected
                                    ? "h-3.5 w-3.5 text-foreground"
                                    : "h-3.5 w-3.5 text-transparent opacity-0"
                                }
                              />
                            </div>
                          </button>
                        );
                      })}

                      {optionRequiresInput ? (
                        <div className="flex items-center gap-2 rounded-[0.45rem] border border-border/60 bg-background/95 px-2 py-2">
                          <Textarea
                            ref={textareaRef}
                            value={currentCustomInput}
                            onChange={(event) =>
                              setCustomAnswerInputs((current) => ({
                                ...current,
                                [currentQuestion.key]: event.target.value,
                              }))
                            }
                            onKeyDown={handleComposerKeyDown}
                            placeholder={copy.structuredInputPlaceholder}
                            rows={2}
                            className="min-h-[3.8rem] flex-1 resize-none text-[12px]"
                            disabled={isStreaming || createFromDraft.isPending || clearDraft.isPending || isRestoringStep}
                          />
                          <div className="flex shrink-0 items-center gap-1 self-start pt-0.5">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              aria-label={copy.backStep}
                              title={copy.backStep}
                              onClick={() => void handleGoBackStep()}
                              disabled={
                                (currentQuestionIndex === 0 && !hasPreviousStructuredStep) ||
                                isStreaming ||
                                createFromDraft.isPending ||
                                isRestoringStep
                              }
                              className="h-8 w-8"
                            >
                              <ChevronLeft className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => void handleStructuredAdvance()}
                              disabled={!currentQuestionReady || isStreaming || createFromDraft.isPending || isRestoringStep}
                              className="min-w-[4.75rem]"
                            >
                              {structuredSubmitLabel}
                            </Button>
                          </div>
                        </div>
                      ) : null}
                    </div>

                    {!optionRequiresInput ? (
                      <div className="flex justify-end border-t border-border/60 bg-[rgb(var(--admin-surface-1)/0.45)] px-3 py-1.5">
                        <div className="flex items-center gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            aria-label={copy.backStep}
                            title={copy.backStep}
                            onClick={() => void handleGoBackStep()}
                            disabled={
                              (currentQuestionIndex === 0 && !hasPreviousStructuredStep) ||
                              isStreaming ||
                              createFromDraft.isPending ||
                              isRestoringStep
                            }
                            className="h-8 w-8"
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void handleStructuredAdvance()}
                            disabled={!currentQuestionReady || isStreaming || createFromDraft.isPending || isRestoringStep}
                            size="sm"
                            className="min-w-[4.75rem]"
                          >
                            {structuredSubmitLabel}
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              {!hasStructuredComposer && !hideStructuredComposer ? (
                <div className="space-y-2">
                  <Label>{copy.freeformLabel}</Label>
                  <div className="relative rounded-[0.75rem] border border-border/60 bg-background/95 p-2">
                    <Textarea
                      ref={textareaRef}
                      value={chatInput}
                      onChange={(event) => setChatInput(event.target.value)}
                      onKeyDown={handleComposerKeyDown}
                      placeholder={copy.chatPlaceholder}
                      rows={5}
                      className="min-h-[8.5rem] border-0 bg-transparent px-1 py-1 pr-24 shadow-none ring-0 focus-visible:ring-0"
                      disabled={isStreaming || createFromDraft.isPending || clearDraft.isPending}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="absolute bottom-3 right-3"
                      onClick={() =>
                        void sendDraftMessage(chatInput.trim(), {
                          checkpointDraft: null,
                        })
                      }
                      disabled={!chatInput.trim() || isStreaming || createFromDraft.isPending || clearDraft.isPending}
                    >
                      {copy.send}
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={planOpen} onOpenChange={setPlanOpen}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>{copy.viewPlan}</DialogTitle>
              <DialogDescription>
                {lang === "zh"
                  ? "查看当前草稿的总结与详细执行计划。"
                  : "Review the current draft summary and detailed execution plan."}
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-2">
              {activeDraft?.summary ? (
                <div className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/70 p-4">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    {copy.draftSummary}
                  </div>
                  <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">
                    {activeDraft.summary}
                  </div>
                </div>
              ) : null}
              {activeDraft?.working_document ? (
                <div className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/70 p-4">
                  <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    {copy.workingDocument}
                  </div>
                  <pre className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">
                    {activeDraft.working_document}
                  </pre>
                </div>
              ) : null}
            </div>
          </DialogContent>
        </Dialog>

        <ConfirmDialog
          open={confirmClearOpen}
          onCancel={() => setConfirmClearOpen(false)}
          onConfirm={handleConfirmClear}
          title={copy.clearDraftConfirmTitle}
          description={copy.clearDraftConfirmDescription}
          confirmLabel={copy.clearDraftConfirmLabel}
          variant="destructive"
          isPending={clearDraft.isPending}
        />

        <ConfirmDialog
          open={confirmCreateOpen}
          onCancel={() => setConfirmCreateOpen(false)}
          onConfirm={() => void handleConfirmCreate()}
          title={createActionReady ? copy.createConfirmTitle : copy.createEarlyConfirmTitle}
          description={createActionReady ? copy.createConfirmDescription : copy.createEarlyConfirmDescription}
          confirmLabel={copy.createConfirmLabel}
          isPending={createFromDraft.isPending}
        />

        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{copy.editTitle}</DialogTitle>
              <DialogDescription>
                {lang === "zh"
                  ? "修改工作流的基础配置、触发事件和执行说明。"
                  : "Edit the workflow configuration, trigger event, and execution instructions."}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>{copy.key}</Label>
                  <Input
                    value={form.key}
                    onChange={(event) => setForm((current) => ({ ...current, key: event.target.value }))}
                    disabled={Boolean(editingKey) || save.isPending}
                    placeholder="comment_moderation_v2"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{copy.name}</Label>
                  <Input
                    value={form.name}
                    onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    disabled={save.isPending}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{copy.trigger}</Label>
                  <Input
                    value={form.trigger_event}
                    onChange={(event) => setForm((current) => ({ ...current, trigger_event: event.target.value }))}
                    disabled={save.isPending}
                    placeholder={copy.triggerPlaceholder}
                  />
                </div>
              </div>

              <AppleSwitch
                checked={form.enabled}
                onCheckedChange={(checked) => setForm((current) => ({ ...current, enabled: checked }))}
                label={form.enabled ? copy.enabled : copy.disabled}
                description={copy.enabledHint}
                disabled={save.isPending}
              />
              <AppleSwitch
                checked={form.require_human_approval}
                onCheckedChange={(checked) =>
                  setForm((current) => ({ ...current, require_human_approval: checked }))
                }
                label={form.require_human_approval ? copy.approval : copy.auto}
                description={copy.approvalHint}
                disabled={save.isPending}
              />

              <div className="flex justify-end">
                <Button
                  onClick={() => save.mutate()}
                  disabled={
                    save.isPending ||
                    !form.key.trim() ||
                    !form.name.trim() ||
                    !form.trigger_event.trim()
                  }
                >
                  {save.isPending ? copy.saving : copy.save}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <AdminSurface eyebrow="Workflow" title={copy.title} description={copy.description}>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{copy.loading}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{copy.empty}</p>
        ) : (
          <div className="grid gap-3">
            {items.map((item) => (
              <div key={item.key} className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/55 px-4 py-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="font-medium text-foreground">{item.name}</div>
                      <Badge variant="outline" className="font-mono">{item.key}</Badge>
                      <Badge variant={item.enabled ? "success" : "secondary"}>
                        {item.enabled ? copy.enabled : copy.disabled}
                      </Badge>
                      <Badge variant={item.require_human_approval ? "info" : "outline"}>
                        {item.require_human_approval ? copy.approval : copy.auto}
                      </Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="outline">
                        {copy.trigger}: {item.trigger_event}
                      </Badge>
                      <Badge variant="info">
                        {copy.runs}: {runCounts.get(item.key) ?? 0}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        setEditingKey(item.key);
                        setForm(toForm(item));
                        setEditOpen(true);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (!window.confirm(copy.deleteConfirm)) {
                          return;
                        }
                        remove.mutate(item.key);
                      }}
                      disabled={remove.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </AdminSurface>
    </div>
  );
}
