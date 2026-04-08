import { useEffect, type ReactNode, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGetQueryKey,
  useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet,
  useUpdateContentSubscriptionConfigApiV1AdminSubscriptionsConfigPut,
} from "@serino/api-client/admin";
import type {
  ContentSubscriptionConfigAdminRead,
  ContentSubscriptionConfigAdminUpdate,
} from "@serino/api-client/models";
import { Loader2, Send } from "lucide-react";
import { toast } from "sonner";
import {
  buildSubscriptionTestFailureMessage,
  sendSubscriptionTestEmail,
} from "@/pages/visitors/api";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";

type MailFieldKey =
  | "smtp_host"
  | "smtp_port"
  | "smtp_from_email"
  | "smtp_username"
  | "smtp_password"
  | "smtp_from_name"
  | "smtp_reply_to";

type HelpLevel = "required" | "recommended" | "optional";
type ConnectionMode = "starttls" | "ssl" | "none";

type FieldHelpCopy = {
  title: string;
  description: string;
  usageTitle: string;
  usageItems: string[];
  level: HelpLevel;
};

type FieldDefinition = {
  key: MailFieldKey;
  label: string;
  type: string;
  value: string;
  placeholder: string;
};

const MAIL_HELP_COPY: Record<
  "zh" | "en",
  Record<MailFieldKey | "connection_mode", FieldHelpCopy>
> = {
  zh: {
    smtp_host: {
      title: "发件邮箱所属服务商提供的 SMTP 服务器地址",
      description:
        "这不是你网站自己的域名，而是邮箱服务商提供的外发邮件服务器地址，通常长得像 smtp.xxx.com。",
      usageTitle: "怎么找",
      usageItems: [
        "去邮箱服务商后台搜索 SMTP、客户端设置、发送服务器",
        "它通常和发件邮箱属于同一服务商",
        "域名邮箱、企业邮箱、云邮件服务都会给出这个地址",
      ],
      level: "required",
    },
    smtp_port: {
      title: "SMTP 服务监听的端口",
      description:
        "端口和连接方式要配套。最常见的是 587 配 STARTTLS，或者 465 配 SSL/TLS。",
      usageTitle: "常见组合",
      usageItems: [
        "587: 推荐给大多数现代 SMTP 服务",
        "465: 常见于 SSL/TLS 直连",
        "如果服务商文档写了别的端口，以它为准",
      ],
      level: "required",
    },
    smtp_from_email: {
      title: "真正对外发信的邮箱地址",
      description:
        "收件人看到的发件地址就是它。必须是 SMTP 服务允许发信的真实邮箱，不能随便写一个占位地址。",
      usageTitle: "注意",
      usageItems: [
        "要和上面的 SMTP 服务对应得上",
        "通常应该和用户名属于同一个邮箱体系",
        "如果服务商限制发件地址，这里必须填受信任地址",
      ],
      level: "required",
    },
    smtp_username: {
      title: "SMTP 登录用户名",
      description:
        "很多服务要求先登录才能发信。常见情况下这里就是邮箱地址，也可能是服务商给的专用用户名。",
      usageTitle: "常见情况",
      usageItems: [
        "企业邮箱和托管邮箱经常需要填写",
        "很多服务要求填完整邮箱地址",
        "如果服务商给了单独的 SMTP Username，就用它",
      ],
      level: "recommended",
    },
    smtp_password: {
      title: "SMTP 登录密码或授权码",
      description:
        "这里经常不是网页登录密码，而是邮箱后台专门生成的授权码或 App Password。",
      usageTitle: "常见情况",
      usageItems: [
        "很多邮箱服务默认要求授权码",
        "如果用户名已填，通常密码也要一起填",
        "普通密码不通时，优先去找授权码/App Password",
      ],
      level: "recommended",
    },
    smtp_from_name: {
      title: "收件箱里显示的发件人名称",
      description:
        "这只是展示名称，不影响 SMTP 连接。不填时系统会回退用站点名。",
      usageTitle: "适合填写",
      usageItems: ["品牌名", "站点名", "例如 Aerisun"],
      level: "optional",
    },
    smtp_reply_to: {
      title: "用户点击回复时要回到的地址",
      description:
        "如果不填，收件人默认回复给发件邮箱。只有想把回复导向另一个地址时才需要填写。",
      usageTitle: "适合填写",
      usageItems: ["客服邮箱", "联系邮箱", "希望和发件账号分离时"],
      level: "optional",
    },
    connection_mode: {
      title: "SMTP 连接方式",
      description:
        "推荐优先按服务商文档配置。大多数现代服务使用 STARTTLS + 587；部分服务使用 SSL/TLS + 465。",
      usageTitle: "推荐",
      usageItems: [
        "默认先试 STARTTLS",
        "如果服务商明确写 465 或 SSL/TLS，再切到 SSL/TLS",
        "不要同时开启两种加密方式",
      ],
      level: "optional",
    },
  },
  en: {
    smtp_host: {
      title: "SMTP server address from your mail provider",
      description:
        "This is not your site domain. It is the outbound mail server address from the mailbox provider, usually something like smtp.xxx.com.",
      usageTitle: "Where to find it",
      usageItems: [
        "Search for SMTP, mail client settings, or outgoing server in the provider dashboard",
        "It should belong to the same provider as the sender mailbox",
        "Hosted mail, business mail, and cloud mail services all expose this value",
      ],
      level: "required",
    },
    smtp_port: {
      title: "Port used by the SMTP service",
      description:
        "The port must match the connection mode. The most common setup is 587 with STARTTLS, or 465 with SSL/TLS.",
      usageTitle: "Common combinations",
      usageItems: [
        "587: recommended for most modern SMTP services",
        "465: common for SSL/TLS direct connections",
        "Use the provider docs if they specify another port",
      ],
      level: "required",
    },
    smtp_from_email: {
      title: "Sender address visible to recipients",
      description:
        "Recipients will see this address as the sender. It must be a real mailbox allowed by the SMTP provider, not a placeholder.",
      usageTitle: "Important",
      usageItems: [
        "It should match the SMTP service above",
        "It usually belongs to the same mailbox system as the username",
        "If the provider restricts sender identities, use an approved address here",
      ],
      level: "required",
    },
    smtp_username: {
      title: "SMTP login username",
      description:
        "Many providers require login before sending. In common setups this is the mailbox address, but some providers give a dedicated SMTP username.",
      usageTitle: "Common cases",
      usageItems: [
        "Often required for hosted and business mail",
        "Many providers expect the full mailbox address",
        "Use the dedicated SMTP username if the provider gives one",
      ],
      level: "recommended",
    },
    smtp_password: {
      title: "SMTP password or app password",
      description:
        "This is often not the normal mailbox password. Many providers require an app password or authorization code for SMTP access.",
      usageTitle: "Common cases",
      usageItems: [
        "App passwords are common for mail services",
        "If username is filled, password is usually needed too",
        "If the normal password fails, look for an app password first",
      ],
      level: "recommended",
    },
    smtp_from_name: {
      title: "Display name shown in the inbox",
      description:
        "This affects presentation only. It does not change SMTP connectivity. If empty, the site name is used as fallback.",
      usageTitle: "Good values",
      usageItems: ["Brand name", "Site title", "For example: Aerisun"],
      level: "optional",
    },
    smtp_reply_to: {
      title: "Reply destination for recipients",
      description:
        "If empty, replies go to the sender mailbox. Fill this only if replies should land in a different inbox.",
      usageTitle: "Useful for",
      usageItems: [
        "Support inboxes",
        "Dedicated contact addresses",
        "Separating replies from the sender account",
      ],
      level: "optional",
    },
    connection_mode: {
      title: "SMTP connection mode",
      description:
        "Follow provider docs when possible. Most modern services use STARTTLS with 587, while some use SSL/TLS with 465.",
      usageTitle: "Recommended",
      usageItems: [
        "Try STARTTLS first in most cases",
        "Switch to SSL/TLS only when the provider explicitly asks for it",
        "Do not enable both encryption modes at the same time",
      ],
      level: "optional",
    },
  },
};

function levelCopy(lang: "zh" | "en", level: HelpLevel) {
  if (lang === "zh") {
    return {
      required: "必填",
      recommended: "常见",
      optional: "可选",
    }[level];
  }
  return {
    required: "Required",
    recommended: "Common",
    optional: "Optional",
  }[level];
}

function levelVariant(level: HelpLevel): "info" | "secondary" | "outline" {
  if (level === "required") return "info";
  if (level === "recommended") return "secondary";
  return "outline";
}

function renderLabel(
  label: string,
  lang: "zh" | "en",
  level: HelpLevel,
): ReactNode {
  return (
    <span className="inline-flex items-center gap-2">
      <span>{label}</span>
      <Badge variant={levelVariant(level)}>{levelCopy(lang, level)}</Badge>
    </span>
  );
}

function helpLevelRank(level: HelpLevel): number {
  if (level === "required") return 0;
  if (level === "recommended") return 1;
  return 2;
}

function getConnectionMode(
  form: ContentSubscriptionConfigAdminUpdate,
): ConnectionMode {
  if (form.smtp_use_ssl) return "ssl";
  if (form.smtp_use_tls) return "starttls";
  return "none";
}

function createSubscriptionForm(
  config?: ContentSubscriptionConfigAdminRead | null,
): ContentSubscriptionConfigAdminUpdate {
  return {
    enabled: config?.enabled ?? false,
    smtp_auth_mode: "password",
    smtp_host: config?.smtp_host ?? "",
    smtp_port: config?.smtp_port ?? 587,
    smtp_username: config?.smtp_username ?? "",
    smtp_password: config?.smtp_password ?? "",
    smtp_oauth_tenant: "",
    smtp_oauth_client_id: "",
    smtp_oauth_client_secret: "",
    smtp_oauth_refresh_token: "",
    smtp_from_email: config?.smtp_from_email ?? "",
    smtp_from_name: config?.smtp_from_name ?? "",
    smtp_reply_to: config?.smtp_reply_to ?? "",
    smtp_use_tls: config?.smtp_use_tls ?? true,
    smtp_use_ssl: config?.smtp_use_ssl ?? false,
  };
}

function buildFormPayload(
  form: ContentSubscriptionConfigAdminUpdate,
): ContentSubscriptionConfigAdminUpdate {
  return {
    enabled: Boolean(form.enabled),
    smtp_auth_mode: "password",
    smtp_host: form.smtp_host?.trim() ?? "",
    smtp_port: Number(form.smtp_port ?? 587),
    smtp_username: form.smtp_username?.trim() ?? "",
    smtp_password: form.smtp_password?.trim() ?? "",
    smtp_oauth_tenant: "",
    smtp_oauth_client_id: "",
    smtp_oauth_client_secret: "",
    smtp_oauth_refresh_token: "",
    smtp_from_email: form.smtp_from_email?.trim() ?? "",
    smtp_from_name: form.smtp_from_name?.trim() ?? "",
    smtp_reply_to: form.smtp_reply_to?.trim() ?? "",
    smtp_use_tls: Boolean(form.smtp_use_tls),
    smtp_use_ssl: Boolean(form.smtp_use_ssl),
  };
}

export function ExternalConfigSection() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const subscriptionConfigQueryKey =
    getGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGetQueryKey();
  const { data: subscriptionRaw, isLoading } =
    useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet();
  const subscriptionConfig = subscriptionRaw?.data as
    | ContentSubscriptionConfigAdminRead
    | undefined;
  const [form, setForm] = useState<ContentSubscriptionConfigAdminUpdate>(() =>
    createSubscriptionForm(),
  );
  const [savedForm, setSavedForm] =
    useState<ContentSubscriptionConfigAdminUpdate>(() =>
      createSubscriptionForm(),
    );
  const [isTesting, setIsTesting] = useState(false);
  const [isSavingWithCheck, setIsSavingWithCheck] = useState(false);
  const [lastCheckOk, setLastCheckOk] = useState<boolean | null>(null);
  const smtpTestPassed = Boolean(
    (subscriptionConfig as { smtp_test_passed?: boolean } | undefined)
      ?.smtp_test_passed,
  );

  useEffect(() => {
    if (!subscriptionConfig) return;
    const nextForm = createSubscriptionForm(subscriptionConfig);
    setForm(nextForm);
    setSavedForm(nextForm);
    setLastCheckOk(Boolean(subscriptionConfig.smtp_test_passed));
  }, [subscriptionConfig]);

  const saveSubscription =
    useUpdateContentSubscriptionConfigApiV1AdminSubscriptionsConfigPut({
      mutation: {
        onSuccess: (response) => {
          if (response?.data) {
            queryClient.setQueryData(subscriptionConfigQueryKey, response);
          }
          void queryClient.invalidateQueries({
            queryKey: subscriptionConfigQueryKey,
          });
          const nextForm = createSubscriptionForm(
            (response?.data as
              | ContentSubscriptionConfigAdminRead
              | undefined) ?? subscriptionConfig,
          );
          setForm(nextForm);
          setSavedForm(nextForm);
          toast.success(t("common.operationSuccess"));
        },
        onError: (error: any) => {
          toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
        },
      },
    });

  if (isLoading) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  const primaryFields: readonly FieldDefinition[] = [
    {
      key: "smtp_host",
      label: t("siteConfig.smtpHost"),
      type: "text",
      value: form.smtp_host ?? "",
      placeholder: "smtp.example.com",
    },
    {
      key: "smtp_port",
      label: t("siteConfig.smtpPort"),
      type: "number",
      value: String(form.smtp_port ?? 587),
      placeholder: "587",
    },
    {
      key: "smtp_from_email",
      label: t("siteConfig.smtpFromEmail"),
      type: "email",
      value: form.smtp_from_email ?? "",
      placeholder: "your-email@example.com",
    },
    {
      key: "smtp_username",
      label: t("siteConfig.smtpUsername"),
      type: "text",
      value: form.smtp_username ?? "",
      placeholder: "your-email@example.com",
    },
    {
      key: "smtp_password",
      label: t("siteConfig.smtpPassword"),
      type: "password",
      value: form.smtp_password ?? "",
      placeholder: "",
    },
    {
      key: "smtp_from_name",
      label: t("siteConfig.smtpFromName"),
      type: "text",
      value: form.smtp_from_name ?? "",
      placeholder: "Aerisun",
    },
  ];

  const advancedFields: readonly FieldDefinition[] = [
    {
      key: "smtp_reply_to",
      label: t("siteConfig.smtpReplyTo"),
      type: "email",
      value: form.smtp_reply_to ?? "",
      placeholder: "hello@example.com",
    },
  ];

  const activeHelp = MAIL_HELP_COPY[lang];
  const connectionMode = getConnectionMode(form);
  primaryFields.sort(
    (a, b) =>
      helpLevelRank(activeHelp[a.key].level) -
      helpLevelRank(activeHelp[b.key].level),
  );
  const hasChanges = JSON.stringify(form) !== JSON.stringify(savedForm);
  const smtpAvailableForCurrentForm = smtpTestPassed && !hasChanges;
  const baseMailReady =
    Boolean(form.smtp_host?.trim()) &&
    Number(form.smtp_port ?? 0) > 0 &&
    Boolean(form.smtp_from_email?.trim());
  const canTestSend =
    baseMailReady &&
    (!form.smtp_username?.trim() || Boolean(form.smtp_password?.trim()));
  const statusTone = isTesting || isSavingWithCheck
    ? "checking"
    : (smtpAvailableForCurrentForm || lastCheckOk === true)
      ? "available"
      : lastCheckOk === false
        ? "invalid"
        : "pending";
  const statusLabel =
    statusTone === "checking"
      ? (lang === "zh" ? "检查中" : "Checking")
      : statusTone === "available"
        ? (lang === "zh" ? "可用" : "Available")
        : statusTone === "invalid"
          ? (lang === "zh" ? "无效" : "Invalid")
          : (lang === "zh" ? "待测试" : "Pending");

  const handleFieldChange = (
    key: keyof ContentSubscriptionConfigAdminUpdate,
    value: string | number | boolean,
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
    setLastCheckOk(null);
  };

  const handleConnectionModeChange = (value: string) => {
    const mode = value as ConnectionMode;
    setLastCheckOk(null);
    setForm((current) => {
      if (mode === "ssl") {
        return {
          ...current,
          smtp_use_tls: false,
          smtp_use_ssl: true,
          smtp_port:
            !current.smtp_port || current.smtp_port === 587
              ? 465
              : current.smtp_port,
        };
      }
      if (mode === "none") {
        return {
          ...current,
          smtp_use_tls: false,
          smtp_use_ssl: false,
        };
      }
      return {
        ...current,
        smtp_use_tls: true,
        smtp_use_ssl: false,
        smtp_port:
          !current.smtp_port || current.smtp_port === 465
            ? 587
            : current.smtp_port,
      };
    });
  };

  const runMailCheck = async (options?: { persistSuccess?: boolean }) => {
    if (!canTestSend) {
      setLastCheckOk(null);
      return false;
    }
    setIsTesting(true);
    try {
      const payload = buildFormPayload(form);
      const result = await sendSubscriptionTestEmail(payload, options);
      setLastCheckOk(true);
      if (options?.persistSuccess) {
        await queryClient.invalidateQueries({
          queryKey: subscriptionConfigQueryKey,
        });
      }
      toast.success(
        lang === "zh"
          ? `测试邮件已发送到 ${result.recipient}`
          : `Test email sent to ${result.recipient}`,
      );
      return true;
    } catch (error) {
      setLastCheckOk(false);
      toast.error(
        error instanceof Error
          ? error.message
          : buildSubscriptionTestFailureMessage(),
      );
      return false;
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    setIsSavingWithCheck(true);
    try {
      await saveSubscription.mutateAsync({ data: buildFormPayload(form) });
      if (canTestSend) {
        await runMailCheck({ persistSuccess: true });
      }
    } finally {
      setIsSavingWithCheck(false);
    }
  };

  return (
    <ConfigSettingsCard
      eyebrow="Mail"
      title={t("more.mailSettings")}
      dirty={hasChanges}
      saving={saveSubscription.isPending || isTesting || isSavingWithCheck}
      saveDisabled={saveSubscription.isPending || isTesting || isSavingWithCheck}
      onSave={() => void handleSave()}
      statusIndicator={{
        label: statusLabel,
        tone: statusTone,
      }}
      testAction={(
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={[
            "gap-2",
            smtpAvailableForCurrentForm
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/16"
              : "",
          ].join(" ")}
          onClick={() => void runMailCheck()}
          disabled={!canTestSend || isTesting || saveSubscription.isPending || isSavingWithCheck}
        >
          {isTesting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          {lang === "zh" ? "测试" : "Test"}
        </Button>
      )}
    >
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (saveSubscription.isPending || isTesting || isSavingWithCheck) {
            return;
          }
          void handleSave();
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          {primaryFields.map((field) => (
            <div key={field.key} className="space-y-2">
              <LabelWithHelp
                htmlFor={field.key}
                label={renderLabel(
                  field.label,
                  lang,
                  activeHelp[field.key].level,
                )}
                title={activeHelp[field.key].title}
                description={activeHelp[field.key].description}
                usageTitle={activeHelp[field.key].usageTitle}
                usageItems={activeHelp[field.key].usageItems}
              />
              <Input
                id={field.key}
                type={field.type}
                autoComplete={
                  field.type === "password"
                    ? "new-password"
                    : field.type === "email"
                      ? "email"
                      : undefined
                }
                value={field.value}
                placeholder={field.placeholder}
                onChange={(event) =>
                  handleFieldChange(
                    field.key,
                    field.key === "smtp_port"
                      ? Number(event.target.value || 0)
                      : event.target.value,
                  )
                }
              />
            </div>
          ))}
        </div>

        <CollapsibleSection
          title={lang === "zh" ? "高级选项" : "Advanced Options"}
          badge={lang === "zh" ? "可选" : "Optional"}
        >
          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              {advancedFields.map((field) => (
                <div key={field.key} className="space-y-2">
                  <LabelWithHelp
                    htmlFor={field.key}
                    label={renderLabel(
                      field.label,
                      lang,
                      activeHelp[field.key].level,
                    )}
                    title={activeHelp[field.key].title}
                    description={activeHelp[field.key].description}
                    usageTitle={activeHelp[field.key].usageTitle}
                    usageItems={activeHelp[field.key].usageItems}
                  />
                  <Input
                    id={field.key}
                    type={field.type}
                    autoComplete={field.type === "email" ? "email" : undefined}
                    value={field.value}
                    placeholder={field.placeholder}
                    onChange={(event) =>
                      handleFieldChange(field.key, event.target.value)
                    }
                  />
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <LabelWithHelp
                htmlFor="connection_mode"
                label={renderLabel(
                  lang === "zh" ? "连接方式" : "Connection Mode",
                  lang,
                  activeHelp.connection_mode.level,
                )}
                title={activeHelp.connection_mode.title}
                description={activeHelp.connection_mode.description}
                usageTitle={activeHelp.connection_mode.usageTitle}
                usageItems={activeHelp.connection_mode.usageItems}
              />
              <Select
                value={connectionMode}
                onValueChange={handleConnectionModeChange}
              >
                <SelectTrigger id="connection_mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="starttls">STARTTLS (587)</SelectItem>
                  <SelectItem value="ssl">SSL/TLS (465)</SelectItem>
                  <SelectItem value="none">
                    {lang === "zh"
                      ? "不加密 / 按服务商自定义"
                      : "No Encryption / Custom"}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CollapsibleSection>
      </form>
    </ConfigSettingsCard>
  );
}
