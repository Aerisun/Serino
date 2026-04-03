import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey,
  useDeleteWebhookApiV1AdminAutomationWebhooksSubscriptionIdDelete,
  useGetWebhooksApiV1AdminAutomationWebhooksGet,
  usePostWebhookApiV1AdminAutomationWebhooksPost,
  usePutWebhookApiV1AdminAutomationWebhooksSubscriptionIdPut,
} from "@serino/api-client/admin";
import type { WebhookSubscriptionCreate, WebhookSubscriptionRead } from "@serino/api-client/models";
import { getAgentWorkflows } from "@/pages/automation/api";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, CheckCircle2 } from "lucide-react";
import { connectTelegramWebhook, testWebhookSubscription } from "@/pages/automation/api";
import { DeliveriesPanel } from "./DeliveriesPage";

type WebhookView = "webhooks" | "deliveries";
const DEFAULT_EVENT_TYPES = ["comment.pending", "guestbook.pending"] as const;
const DEFAULT_TIMEOUT_SECONDS = 10;
const DEFAULT_MAX_ATTEMPTS = 6;

type WebhookProvider = "feishu" | "telegram";

interface WebhookFormState {
  name: string;
  provider: WebhookProvider;
  feishu_webhook_url: string;
  feishu_secret: string;
  telegram_bot_token: string;
  telegram_chat_id: string;
  event_types: string[];
  status: string;
  timeout_seconds: number;
  max_attempts: number;
}

type TelegramConnectStatus = "idle" | "pending" | "success" | "error";

interface TelegramConnectState {
  status: TelegramConnectStatus;
  message: string;
}

type WebhookSubscriptionRow = WebhookSubscriptionRead & {
  last_test_status?: string | null;
  last_test_error?: string | null;
  last_tested_at?: string | null;
};

const EMPTY_FORM: WebhookFormState = {
  name: "",
  provider: "feishu",
  feishu_webhook_url: "",
  feishu_secret: "",
  telegram_bot_token: "",
  telegram_chat_id: "",
  event_types: [...DEFAULT_EVENT_TYPES],
  status: "active",
  timeout_seconds: DEFAULT_TIMEOUT_SECONDS,
  max_attempts: DEFAULT_MAX_ATTEMPTS,
};

const EMPTY_TELEGRAM_CONNECT_STATE: TelegramConnectState = {
  status: "idle",
  message: "",
};

function normalizeProvider(value: string): WebhookProvider {
  return value === "telegram" ? "telegram" : "feishu";
}

function detectProvider(targetUrl: string): WebhookProvider {
  return targetUrl.toLowerCase().includes("api.telegram.org") ? "telegram" : "feishu";
}

function parseTelegramWebhookUrl(targetUrl: string) {
  try {
    const url = new URL(targetUrl);
    const tokenMatch = url.pathname.match(/^\/bot([^/]+)\/sendMessage$/i);
    return {
      bot_token: tokenMatch?.[1] ?? "",
      chat_id: url.searchParams.get("chat_id") ?? "",
    };
  } catch {
    return {
      bot_token: "",
      chat_id: "",
    };
  }
}

function buildTelegramWebhookUrl(botToken: string, chatId: string) {
  const url = new URL(`https://api.telegram.org/bot${botToken.trim()}/sendMessage`);
  url.searchParams.set("chat_id", chatId.trim());
  return url.toString();
}

function buildWebhookPayload(
  form: WebhookFormState,
  { allowBlankName = false }: { allowBlankName?: boolean } = {},
): WebhookSubscriptionCreate {
  const provider = normalizeProvider(form.provider);
  const name = form.name.trim();
  return {
    name: name || (allowBlankName ? "Webhook test" : ""),
    target_url:
      provider === "telegram"
        ? buildTelegramWebhookUrl(form.telegram_bot_token, form.telegram_chat_id)
        : form.feishu_webhook_url.trim(),
    event_types: [...form.event_types],
    secret: provider === "feishu" ? form.feishu_secret.trim() || null : null,
    timeout_seconds: form.timeout_seconds || DEFAULT_TIMEOUT_SECONDS,
    max_attempts: form.max_attempts || DEFAULT_MAX_ATTEMPTS,
    status: form.status,
    headers: {},
  };
}

function isFeishuReady(form: WebhookFormState) {
  return Boolean(form.feishu_webhook_url.trim());
}

function isTelegramReady(form: WebhookFormState) {
  return Boolean(form.telegram_bot_token.trim() && form.telegram_chat_id.trim());
}

function resolveWebhookStatusState(row: WebhookSubscriptionRow, lang: "zh" | "en") {
  const normalized = row.status.trim().toLowerCase();
  if (normalized !== "active") {
    return {
      label: lang === "zh" ? "停用" : "Inactive",
      tone: "inactive" as const,
      detail: row.status,
    };
  }

  if (row.last_test_status === "failed") {
    return {
      label: lang === "zh" ? "失败" : "Failed",
      tone: "failed" as const,
      detail: row.last_test_error || (lang === "zh" ? "上次测试失败" : "Last test failed"),
    };
  }

  return {
    label: lang === "zh" ? "正常" : "Normal",
    tone: "normal" as const,
    detail: row.last_test_status === "succeeded"
      ? (lang === "zh" ? "上次测试通过" : "Last test passed")
      : (lang === "zh" ? "尚未测试" : "Not tested yet"),
  };
}

function subscriptionToPayload(row: WebhookSubscriptionRead, status: string): WebhookSubscriptionCreate {
  return {
    name: row.name,
    target_url: row.target_url,
    event_types: [...(row.event_types ?? [])],
    secret: row.secret ?? null,
    timeout_seconds: row.timeout_seconds ?? DEFAULT_TIMEOUT_SECONDS,
    max_attempts: row.max_attempts ?? DEFAULT_MAX_ATTEMPTS,
    status,
    headers: row.headers ?? {},
  };
}

function collectLinkedWorkflowNames(
  subscriptionId: string,
  workflows: Array<{ key: string; name: string; graph: { nodes?: Array<{ type?: string; config?: Record<string, unknown> }> } }>,
) {
  return workflows
    .filter((workflow) => {
      const nodes = Array.isArray(workflow.graph?.nodes) ? workflow.graph.nodes : [];
      return nodes.some((node) => {
        if (node?.type !== "notification.webhook") return false;
        const linkedIds = Array.isArray(node.config?.linked_subscription_ids)
          ? node.config.linked_subscription_ids
          : [];
        return linkedIds.some((item) => String(item) === subscriptionId);
      });
    })
    .map((workflow) => workflow.name || workflow.key);
}

function buildFieldHelp(lang: "zh" | "en") {
  if (lang === "zh") {
    return {
      feishuWebhook: {
        label: "Feishu Webhook URL",
        description: "从飞书群机器人里复制 webhook 地址。",
        usageTitle: "从哪拿",
        usageItems: [
          "群聊 -> 群设置 -> 群机器人 -> 添加机器人 -> 自定义机器人",
          "复制 webhook URL，整段贴到这里即可",
        ],
      },
      feishuSecret: {
        label: "Secret",
        description: "如果机器人开启了签名校验，这里填安全密钥。",
        usageTitle: "从哪拿",
        usageItems: ["飞书机器人安全设置里的 Secret"],
      },
      telegramToken: {
        label: "bot_token",
        description: "Telegram Bot API 路径中的 token 参数（/bot<token>/sendMessage）。",
        usageTitle: "从哪拿",
        usageItems: [
          "在 @BotFather 创建 bot 后复制 token",
          "官方示例：https://api.telegram.org/bot<token>/sendMessage",
        ],
      },
      telegramChatId: {
        label: "chat_id",
        description: "sendMessage 的 chat_id 参数。可填数字 ID 或 @channelusername。",
        usageTitle: "从哪拿",
        usageItems: [
          "官方参数名就是 chat_id",
          "群聊/超级群一般是数字 ID，频道可用 @channelusername",
        ],
      },
    };
  }

  return {
    feishuWebhook: {
      label: "Feishu Webhook URL",
      description: "Copy the webhook URL from the Feishu group bot settings.",
      usageTitle: "Where to get it",
      usageItems: [
        "Group chat -> Group settings -> Group bot -> Add bot -> Custom bot",
        "Copy the webhook URL and paste the full string here",
      ],
    },
    feishuSecret: {
      label: "Secret",
      description: "Fill this only if the robot uses signature verification.",
      usageTitle: "Where to get it",
      usageItems: ["The Secret from the Feishu bot security settings"],
    },
    telegramToken: {
      label: "bot_token",
      description: "The token parameter in Telegram Bot API path (/bot<token>/sendMessage).",
      usageTitle: "Where to get it",
      usageItems: [
        "Create the bot with @BotFather and copy the token",
        "Official pattern: https://api.telegram.org/bot<token>/sendMessage",
      ],
    },
    telegramChatId: {
      label: "chat_id",
      description: "The chat_id parameter for sendMessage. Use numeric ID or @channelusername.",
      usageTitle: "Where to get it",
      usageItems: [
        "Official parameter name is chat_id",
        "Groups and supergroups usually use numeric IDs, channels can use @channelusername",
      ],
    },
  };
}

export function WebhooksPanel() {
  const { lang, t } = useI18n();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<WebhookSubscriptionRead | null>(null);
  const [form, setForm] = useState<WebhookFormState>(EMPTY_FORM);
  const [telegramConnectState, setTelegramConnectState] = useState<TelegramConnectState>(EMPTY_TELEGRAM_CONNECT_STATE);
  const telegramConnectRequestIdRef = useRef(0);
  const { data: raw, isLoading } = useGetWebhooksApiV1AdminAutomationWebhooksGet();
  const { data: workflows } = useQuery({
    queryKey: ["admin", "agent", "workflows"],
    queryFn: getAgentWorkflows,
  });
  const items = (raw?.data ?? []) as WebhookSubscriptionRow[];
  const linkedWorkflowNamesBySubscriptionId = useMemo(() => {
    const workflowList = (workflows ?? []) as Array<{
      key: string;
      name: string;
      graph: { nodes?: Array<{ type?: string; config?: Record<string, unknown> }> };
    }>;
    return new Map(
      items.map((row) => [row.id, collectLinkedWorkflowNames(row.id, workflowList)]),
    );
  }, [items, workflows]);
  const help = buildFieldHelp(lang);

  const resetTelegramConnectState = () => {
    // Invalidate any in-flight connect callbacks so stale results do not override current form state.
    telegramConnectRequestIdRef.current += 1;
    setTelegramConnectState(EMPTY_TELEGRAM_CONNECT_STATE);
  };

  const resetForm = () => {
    setForm(EMPTY_FORM);
    resetTelegramConnectState();
  };

  const createWebhook = usePostWebhookApiV1AdminAutomationWebhooksPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        setOpen(false);
        setEditing(null);
        resetForm();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const updateWebhook = usePutWebhookApiV1AdminAutomationWebhooksSubscriptionIdPut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        setOpen(false);
        setEditing(null);
        resetForm();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const deleteWebhook = useDeleteWebhookApiV1AdminAutomationWebhooksSubscriptionIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const testWebhook = useMutation({
    mutationFn: ({ payload, subscriptionId }: { payload: WebhookSubscriptionCreate; subscriptionId?: string }) =>
      testWebhookSubscription(payload, { subscriptionId }),
    onSuccess: async (result, variables) => {
      if (variables.subscriptionId) {
        await queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
      }
      if (result.ok) {
        toast.success(lang === "zh" ? `测试成功：${result.provider}` : `Test succeeded: ${result.provider}`);
        return;
      }
      toast.error(result.summary || (lang === "zh" ? "测试失败" : "Test failed"));
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const connectTelegram = useMutation({
    mutationFn: (botToken: string) => connectTelegramWebhook(botToken, true),
    onMutate: () => {
      const requestId = telegramConnectRequestIdRef.current + 1;
      telegramConnectRequestIdRef.current = requestId;
      setTelegramConnectState({
        status: "pending",
        message: "",
      });
      return { requestId };
    },
    onSuccess: (result, _botToken, context) => {
      if (!context || context.requestId !== telegramConnectRequestIdRef.current) {
        return;
      }
      if (result.ok && result.chat_id !== undefined && result.chat_id !== null && String(result.chat_id).trim()) {
        const nextChatId = String(result.chat_id).trim();
        setForm((prev) => ({ ...prev, telegram_chat_id: nextChatId }));
        setTelegramConnectState({
          status: "success",
          message: "",
        });
        toast.success(lang === "zh" ? "Telegram 连接成功" : "Telegram connected");
        return;
      }

      const fallback = lang === "zh" ? "连接失败，请先给机器人发送消息后重试。" : "Connection failed. Send a message to the bot, then retry.";
      setTelegramConnectState({
        status: "error",
        message: result.summary || fallback,
      });
      toast.error(result.summary || fallback);
    },
    onError: (error: Error, _botToken, context) => {
      if (!context || context.requestId !== telegramConnectRequestIdRef.current) {
        return;
      }
      const fallback = lang === "zh" ? "连接失败，请检查 token 或网络。" : "Connection failed. Check token or network.";
      setTelegramConnectState({
        status: "error",
        message: error.message || fallback,
      });
      toast.error(error.message || fallback);
    },
  });

  const openCreate = () => {
    setEditing(null);
    resetForm();
    setOpen(true);
  };

  const openEdit = (row: WebhookSubscriptionRead) => {
    const provider = detectProvider(row.target_url);
    resetTelegramConnectState();
    setEditing(row);
    if (provider === "telegram") {
      const telegram = parseTelegramWebhookUrl(row.target_url);
      setForm({
        name: row.name,
        provider,
        feishu_webhook_url: "",
        feishu_secret: "",
        telegram_bot_token: telegram.bot_token,
        telegram_chat_id: telegram.chat_id,
        event_types: row.event_types.length ? row.event_types : [...DEFAULT_EVENT_TYPES],
        status: row.status,
        timeout_seconds: row.timeout_seconds ?? DEFAULT_TIMEOUT_SECONDS,
        max_attempts: row.max_attempts ?? DEFAULT_MAX_ATTEMPTS,
      });
      setOpen(true);
      return;
    }

    setForm({
      name: row.name,
      provider,
      feishu_webhook_url: row.target_url,
      feishu_secret: row.secret ?? "",
      telegram_bot_token: "",
      telegram_chat_id: "",
      event_types: row.event_types.length ? row.event_types : [...DEFAULT_EVENT_TYPES],
      status: row.status,
      timeout_seconds: row.timeout_seconds ?? DEFAULT_TIMEOUT_SECONDS,
      max_attempts: row.max_attempts ?? DEFAULT_MAX_ATTEMPTS,
    });
    setOpen(true);
  };

  const submit = () => {
    const payload = buildWebhookPayload(form);
    if (!payload.name) {
      toast.error(lang === "zh" ? "请先填写名称" : "Name is required");
      return;
    }
    if (!payload.target_url) {
      toast.error(lang === "zh" ? "请先选择渠道并填写必要信息" : "Select a provider and fill the required fields");
      return;
    }
    if (editing) {
      updateWebhook.mutate({ subscriptionId: editing.id, data: payload });
      return;
    }
    createWebhook.mutate({ data: payload });
  };

  const runTest = () => {
    const payload = buildWebhookPayload(form, { allowBlankName: true });
    if (!payload.target_url) {
      toast.error(lang === "zh" ? "请先选择渠道并填写必要信息" : "Select a provider and fill the required fields");
      return;
    }
    testWebhook.mutate({ payload, subscriptionId: editing?.id });
  };

  const runTelegramConnect = () => {
    const botToken = form.telegram_bot_token.trim();
    if (!botToken) {
      toast.error(lang === "zh" ? "请先填写 bot_token" : "Please fill bot_token first");
      return;
    }
    setForm((prev) => ({ ...prev, telegram_chat_id: "" }));
    connectTelegram.mutate(botToken);
  };

  const isTelegramConnecting = telegramConnectState.status === "pending";

  return (
    <>
      <AdminSurface
        eyebrow="Webhook"
        title={t("automation.webhooks")}
        description={t("automation.webhooksDescription")}
        actions={(
          <Button size="sm" onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            {t("common.create")}
          </Button>
        )}
      >
        <Dialog
          open={open}
          onOpenChange={(nextOpen) => {
            setOpen(nextOpen);
            if (!nextOpen) {
              setEditing(null);
              resetForm();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editing ? t("common.edit") : t("common.create")}</DialogTitle>
              <DialogDescription>
                {lang === "zh"
                  ? "配置 Webhook 订阅。Telegram 可通过连接按钮自动完成目标配置。"
                  : "Configure webhook subscriptions. Telegram target can be auto-configured via Connect."}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <AdminSegmentedFilter
                value={form.provider}
                onValueChange={(value) => {
                  setForm((p) => ({ ...p, provider: normalizeProvider(value) }));
                  resetTelegramConnectState();
                }}
                items={[
                  { value: "feishu", label: "Feishu" },
                  { value: "telegram", label: "Telegram" },
                ]}
                width="content"
                tone="accent"
              />

              <div className="space-y-1">
                <LabelWithHelp
                  label={lang === "zh" ? "名称" : "Name"}
                  htmlFor="webhook-name"
                  description={lang === "zh" ? "这只是后台里辨认订阅用的名字。" : "A label for identifying the subscription in the admin UI."}
                  usageTitle={lang === "zh" ? "用途" : "Usage"}
                  usageItems={[
                    lang === "zh" ? "会显示在 Webhook 订阅列表里" : "Shown in the subscription list",
                  ]}
                />
                <Input
                  id="webhook-name"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                />
              </div>

              {form.provider === "feishu" ? (
                <>
                  <div className="space-y-1">
                    <LabelWithHelp
                      label={help.feishuWebhook.label}
                      htmlFor="feishu-webhook-url"
                      description={help.feishuWebhook.description}
                      usageTitle={help.feishuWebhook.usageTitle}
                      usageItems={help.feishuWebhook.usageItems}
                    />
                    <Input
                      id="feishu-webhook-url"
                      value={form.feishu_webhook_url}
                      onChange={(e) => setForm((p) => ({ ...p, feishu_webhook_url: e.target.value }))}
                      placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                    />
                  </div>
                  <div className="space-y-1">
                    <LabelWithHelp
                      label={help.feishuSecret.label}
                      htmlFor="feishu-secret"
                      description={help.feishuSecret.description}
                      usageTitle={help.feishuSecret.usageTitle}
                      usageItems={help.feishuSecret.usageItems}
                    />
                    <Input
                      id="feishu-secret"
                      value={form.feishu_secret}
                      onChange={(e) => setForm((p) => ({ ...p, feishu_secret: e.target.value }))}
                      placeholder={lang === "zh" ? "可选" : "Optional"}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-1">
                    <LabelWithHelp
                      label={help.telegramToken.label}
                      htmlFor="telegram-bot-token"
                      description={help.telegramToken.description}
                      usageTitle={help.telegramToken.usageTitle}
                      usageItems={help.telegramToken.usageItems}
                    />
                    <Input
                      id="telegram-bot-token"
                      value={form.telegram_bot_token}
                      onChange={(e) => {
                        const nextValue = e.target.value;
                        setForm((p) => ({ ...p, telegram_bot_token: nextValue }));
                        if (telegramConnectState.status !== "idle") {
                          resetTelegramConnectState();
                        }
                      }}
                      placeholder="123456:ABC-DEF..."
                    />
                  </div>
                </>
              )}

              <div className="flex flex-wrap justify-end gap-2">
                {form.provider === "feishu" ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={runTest}
                    disabled={
                      testWebhook.isPending ||
                      createWebhook.isPending ||
                      updateWebhook.isPending ||
                      !isFeishuReady(form)
                    }
                  >
                    {testWebhook.isPending
                      ? (lang === "zh" ? "测试中..." : "Testing...")
                      : (lang === "zh" ? "测试连接" : "Test Connection")}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant={telegramConnectState.status === "success" ? "default" : "outline"}
                    className={telegramConnectState.status === "success"
                      ? "border-green-600 bg-green-600 text-white hover:bg-green-700"
                      : undefined}
                    onClick={runTelegramConnect}
                    disabled={isTelegramConnecting || !form.telegram_bot_token.trim()}
                  >
                    {isTelegramConnecting
                      ? (lang === "zh" ? "连接中..." : "Connecting...")
                      : telegramConnectState.status === "success"
                        ? (
                          <>
                            <CheckCircle2 className="mr-2 h-4 w-4" />
                            {lang === "zh" ? "已连接" : "Connected"}
                          </>
                        )
                        : (lang === "zh" ? "自动配置连接" : "Auto Connect")}
                  </Button>
                )}
                <Button
                  onClick={submit}
                  disabled={
                    createWebhook.isPending ||
                    updateWebhook.isPending ||
                    (!form.name.trim() && !editing) ||
                    (form.provider === "feishu"
                      ? !isFeishuReady(form)
                      : !isTelegramReady(form))
                  }
                >
                  {editing ? t("common.save") : t("common.create")}
                </Button>
              </div>
              {form.provider === "telegram" && telegramConnectState.status === "error" && telegramConnectState.message ? (
                <p className="text-xs text-muted-foreground text-right">{telegramConnectState.message}</p>
              ) : null}
            </div>
          </DialogContent>
        </Dialog>
        <DataTable<WebhookSubscriptionRow>
          columns={[
            { header: t("common.name"), accessor: "name" },
            {
              header: t("automation.status"),
              accessor: (row) => {
                const statusState = resolveWebhookStatusState(row, lang);
                const className = statusState.tone === "normal"
                  ? "inline-flex items-center rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300"
                  : statusState.tone === "failed"
                    ? "inline-flex items-center rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-700 dark:text-red-300"
                    : "inline-flex items-center rounded-full border border-zinc-500/30 bg-zinc-500/10 px-2.5 py-1 text-xs font-medium text-zinc-700 dark:text-zinc-300";

                return (
                  <span
                    className={className}
                    aria-label={`${t("automation.status")}: ${statusState.label}`}
                    title={statusState.detail}
                  >
                    {statusState.label}
                    {statusState.tone === "normal" ? (
                      <span className="ml-1.5 h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_2px_rgba(16,185,129,0.25),0_0_10px_rgba(16,185,129,0.95)]" />
                    ) : null}
                  </span>
                );
              },
            },
            {
              header: t("common.actions"),
              className: "w-[220px] text-center",
              accessor: (row) => (
                <div className="flex justify-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      updateWebhook.mutate({
                        subscriptionId: row.id,
                        data: subscriptionToPayload(row, row.status === "active" ? "inactive" : "active"),
                      })}
                  >
                    {row.status === "active"
                      ? (lang === "zh" ? "停用" : "Disable")
                      : (lang === "zh" ? "启用" : "Enable")}
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => openEdit(row)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => deleteWebhook.mutate({ subscriptionId: row.id })}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ),
            },
          ]}
          data={items}
          isLoading={isLoading}
          renderExpandedRow={(row) => {
            const names = linkedWorkflowNamesBySubscriptionId.get(row.id) ?? [];
            return (
              <div className="py-4">
                <div className="text-sm font-medium text-foreground/90">
                  {lang === "zh" ? "参与的工作流" : "Linked workflows"}
                </div>
                {names.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {names.map((name) => (
                      <span
                        key={name}
                        className="inline-flex items-center rounded-full border border-border/70 bg-background px-3 py-1 text-sm text-foreground/90"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="mt-2 text-sm text-muted-foreground">
                    {lang === "zh" ? "当前还没有工作流使用这个 Webhook。" : "No workflow is using this webhook yet."}
                  </div>
                )}
              </div>
            );
          }}
        />
      </AdminSurface>
    </>
  );
}

export function WebhookManagementSwitcher() {
  const { lang } = useI18n();
  const [view, setView] = useState<WebhookView>("webhooks");

  const viewCopy = lang === "zh"
    ? {
        webhooks: "Webhook 配置",
        deliveries: "投递记录",
      }
    : {
        webhooks: "Webhook Config",
        deliveries: "Deliveries",
      };

  return (
    <div className="space-y-4">
      <AdminSegmentedFilter
        value={view}
        onValueChange={(next) => setView(next as WebhookView)}
        items={[
          { value: "webhooks", label: viewCopy.webhooks },
          { value: "deliveries", label: viewCopy.deliveries },
        ]}
        width="content"
      />
      {view === "webhooks" ? <WebhooksPanel /> : <DeliveriesPanel />}
    </div>
  );
}

export default function WebhooksPage() {
  const { t } = useI18n();

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("automation.webhooks")}
        description={t("automation.webhooksDescription")}
      />
      <WebhookManagementSwitcher />
    </div>
  );
}
