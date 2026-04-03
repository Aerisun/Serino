import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import {
  getGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGetQueryKey,
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateContentSubscriptionConfigApiV1AdminSubscriptionsConfigPut,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
} from "@serino/api-client/admin";
import type { SiteProfileAdminRead } from "@serino/api-client/models";
import { toast } from "sonner";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Card, CardContent } from "@/components/ui/Card";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { cn } from "@/lib/utils";

const FEATURE_FLAGS = ["toc", "reading_progress"] as const;
const SUBSCRIPTION_CONTENT_OPTIONS = [
  { key: "posts", label: "文章" },
  { key: "diary", label: "日记" },
  { key: "thoughts", label: "想法" },
  { key: "excerpts", label: "摘录" },
] as const;
const DEFAULT_SUBSCRIPTION_SUBJECT_TEMPLATE = "[{site_name}] {content_title}";
const DEFAULT_SUBSCRIPTION_BODY_TEMPLATE =
  "{site_name} 有新的{content_type_label}内容发布。\n\n{content_title}\n{content_summary}\n\n阅读链接：{content_url}\nRSS：{feed_url}";
const SUBSCRIPTION_TEMPLATE_FIELD_CLASS =
  "mx-px w-[calc(100%-2px)] max-w-full border-border/70 bg-background/72 shadow-none [backdrop-filter:none] [-webkit-backdrop-filter:none] focus:!border-[rgb(var(--admin-accent-rgb)/0.36)] focus:shadow-none focus-visible:!ring-[rgb(var(--admin-accent-rgb)/0.26)] focus-visible:!ring-offset-0";

type SubscriptionContentType = (typeof SUBSCRIPTION_CONTENT_OPTIONS)[number]["key"];

interface AdvancedSubscriptionForm {
  allowed_content_types: SubscriptionContentType[];
  mail_subject_template: string;
  mail_body_template: string;
}

type SubscriptionConfigWithAdvanced = {
  enabled?: boolean;
  smtp_test_passed?: boolean;
  allowed_content_types?: string[];
  mail_subject_template?: string;
  mail_body_template?: string;
};

function createAdvancedSubscriptionForm(
  config?: SubscriptionConfigWithAdvanced,
): AdvancedSubscriptionForm {
  const allowedSet = new Set(
    (config?.allowed_content_types ?? [])
      .map((item) => String(item).trim())
      .filter((item): item is SubscriptionContentType =>
        SUBSCRIPTION_CONTENT_OPTIONS.some((option) => option.key === item),
      ),
  );
  const fallbackTypes = SUBSCRIPTION_CONTENT_OPTIONS.map((item) => item.key);
  return {
    allowed_content_types:
      allowedSet.size > 0
        ? SUBSCRIPTION_CONTENT_OPTIONS
            .map((item) => item.key)
            .filter((key) => allowedSet.has(key))
        : fallbackTypes,
    mail_subject_template:
      config?.mail_subject_template?.trim() ||
      DEFAULT_SUBSCRIPTION_SUBJECT_TEMPLATE,
    mail_body_template:
      config?.mail_body_template?.trim() ||
      DEFAULT_SUBSCRIPTION_BODY_TEMPLATE,
  };
}

function isSameAdvancedForm(
  left: AdvancedSubscriptionForm,
  right: AdvancedSubscriptionForm,
): boolean {
  return (
    left.mail_subject_template === right.mail_subject_template &&
    left.mail_body_template === right.mail_body_template &&
    left.allowed_content_types.length === right.allowed_content_types.length &&
    left.allowed_content_types.every((item, index) => item === right.allowed_content_types[index])
  );
}

export function FeatureTogglesSection() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const { data: subscriptionRaw, isLoading: subscriptionLoading } =
    useGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGet();
  const profile = raw?.data as SiteProfileAdminRead | undefined;
  const subscriptionConfig =
    (subscriptionRaw?.data as SubscriptionConfigWithAdvanced | undefined) ??
    undefined;
  const smtpTestPassed = Boolean(
    subscriptionConfig?.smtp_test_passed,
  );
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});
  const [subscriptionEnabled, setSubscriptionEnabled] = useState(false);
  const [advancedForm, setAdvancedForm] = useState<AdvancedSubscriptionForm>(() =>
    createAdvancedSubscriptionForm(),
  );
  const [savedAdvancedForm, setSavedAdvancedForm] =
    useState<AdvancedSubscriptionForm>(() => createAdvancedSubscriptionForm());
  const [advancedExpanded, setAdvancedExpanded] = useState(false);

  useEffect(() => {
    if (profile) {
      setFeatureFlags(profile.feature_flags ?? {});
    }
  }, [profile]);

  useEffect(() => {
    if (subscriptionConfig) {
      setSubscriptionEnabled(Boolean(subscriptionConfig.enabled));
      const nextForm = createAdvancedSubscriptionForm(subscriptionConfig);
      setAdvancedForm(nextForm);
      setSavedAdvancedForm(nextForm);
    }
  }, [subscriptionConfig]);

  useEffect(() => {
    if (!(smtpTestPassed && subscriptionEnabled)) {
      setAdvancedExpanded(false);
    }
  }, [smtpTestPassed, subscriptionEnabled]);

  const saveProfile = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
        });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const saveSubscription = useUpdateContentSubscriptionConfigApiV1AdminSubscriptionsConfigPut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetContentSubscriptionConfigApiV1AdminSubscriptionsConfigGetQueryKey(),
        });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const resolvedFeatureFlags = useMemo(
    () =>
      FEATURE_FLAGS.reduce<Record<string, boolean>>((acc, key) => {
        acc[key] = featureFlags[key] ?? true;
        return acc;
      }, {}),
    [featureFlags],
  );

  if (isLoading || subscriptionLoading) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  const flags = [
    {
      key: "toc",
      label: t("siteConfig.featureToc"),
      desc: t("siteConfig.featureTocDesc"),
    },
    {
      key: "reading_progress",
      label: t("siteConfig.featureReadingProgress"),
      desc: t("siteConfig.featureReadingProgressDesc"),
    },
  ] as const;

  const buildSaveData = (nextFeatureFlags: Record<string, boolean>) => ({
    name: profile?.name ?? "",
    title: profile?.title ?? "",
    bio: profile?.bio ?? "",
    role: profile?.role ?? "",
    hero_video_url: profile?.hero_video_url ?? "",
    feature_flags: nextFeatureFlags,
  });

  const handleFeatureToggle = async (flagKey: string) => {
    const previousFlags = featureFlags;
    const nextFeatureFlags = {
      ...featureFlags,
      [flagKey]: !resolvedFeatureFlags[flagKey],
    };

    setFeatureFlags(nextFeatureFlags);

    try {
      await saveProfile.mutateAsync({ data: buildSaveData(nextFeatureFlags) });
    } catch {
      setFeatureFlags(previousFlags);
    }
  };

  const handleSubscriptionToggle = async (nextEnabled: boolean) => {
    const previousEnabled = subscriptionEnabled;
    setSubscriptionEnabled(nextEnabled);

    try {
      await saveSubscription.mutateAsync({ data: { enabled: nextEnabled } });
      if (nextEnabled && !smtpTestPassed) {
        toast.warning(t("siteConfig.contentSubscriptionServiceNotConfigured"));
      }
    } catch {
      setSubscriptionEnabled(previousEnabled);
    }
  };

  const toggleAllowedContentType = (contentType: SubscriptionContentType) => {
    setAdvancedForm((current) => {
      const enabled = current.allowed_content_types.includes(contentType);
      if (enabled && current.allowed_content_types.length === 1) {
        toast.warning(t("siteConfig.contentSubscriptionAdvancedAtLeastOneType"));
        return current;
      }
      const nextTypes = enabled
        ? current.allowed_content_types.filter((item) => item !== contentType)
        : [...current.allowed_content_types, contentType];
      return {
        ...current,
        allowed_content_types: SUBSCRIPTION_CONTENT_OPTIONS
          .map((item) => item.key)
          .filter((item) => nextTypes.includes(item)),
      };
    });
  };

  const saveAdvancedSettings = async () => {
    try {
      const payload = {
        allowed_content_types: advancedForm.allowed_content_types,
        mail_subject_template: advancedForm.mail_subject_template,
        mail_body_template: advancedForm.mail_body_template,
      };
      await saveSubscription.mutateAsync({ data: payload as any });
      setSavedAdvancedForm(advancedForm);
    } catch {
      // The mutation handler already provides user-facing feedback.
    }
  };

  const subscriptionStatus = smtpTestPassed
    ? t("siteConfig.contentSubscriptionAvailable")
    : t("siteConfig.contentSubscriptionUnavailable");
  const subscriptionReminder =
    subscriptionEnabled && !smtpTestPassed
      ? ` · ${t("siteConfig.contentSubscriptionServiceNotConfigured")}`
      : "";
  const subscriptionDescription = smtpTestPassed
    ? `${subscriptionStatus}${subscriptionReminder} · ${t("siteConfig.contentSubscriptionConfigHint")}`
    : t("siteConfig.contentSubscriptionSetupGuide");
  const advancedDirty = !isSameAdvancedForm(advancedForm, savedAdvancedForm);
  const canExpandAdvanced = smtpTestPassed && subscriptionEnabled;

  return (
    <div className="mt-4 space-y-5">
      <Card className="max-w-2xl">
        <CardContent className="space-y-4 pt-6">
          <div>
            <h3 className="text-lg font-semibold">{t("siteConfig.featureFlags")}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("siteConfig.featureFlagsDescription")}
            </p>
          </div>

          <div className="space-y-4">
            {flags.map((flag) => (
              <AppleSwitch
                key={flag.key}
                checked={resolvedFeatureFlags[flag.key]}
                onCheckedChange={() => void handleFeatureToggle(flag.key)}
                label={flag.label}
                description={flag.desc}
                disabled={saveProfile.isPending}
              />
            ))}

            <AppleSwitch
              checked={subscriptionEnabled}
              onCheckedChange={(checked) => void handleSubscriptionToggle(checked)}
              switchLeading={
                canExpandAdvanced ? (
                  <button
                    type="button"
                    aria-label={advancedExpanded ? t("common.collapse") : t("common.expand")}
                    aria-expanded={advancedExpanded}
                    disabled={saveSubscription.isPending}
                    onClick={() => setAdvancedExpanded((current) => !current)}
                    className={cn(
                      "inline-flex h-6 w-6 items-center justify-center rounded-md border border-border/70 bg-background/40 text-muted-foreground transition hover:bg-background/70 hover:text-foreground",
                      saveSubscription.isPending && "cursor-not-allowed opacity-60",
                      advancedExpanded && "text-foreground",
                    )}
                  >
                    <ChevronRight
                      className={cn(
                        "h-4 w-4 transition-transform duration-200",
                        advancedExpanded && "rotate-90",
                      )}
                    />
                  </button>
                ) : null
              }
              label={t("siteConfig.contentSubscriptionEnabled")}
              description={subscriptionDescription}
              descriptionClassName={
                smtpTestPassed ? undefined : "text-amber-600 dark:text-amber-300"
              }
              expandableOpen={canExpandAdvanced && advancedExpanded}
              expandableContent={
                  canExpandAdvanced ? (
                    <div className="space-y-4">
                      <div className="flex items-start justify-between gap-3">
                        <h4 className="text-sm font-semibold">
                          {t("siteConfig.contentSubscriptionAdvancedTitle")}
                        </h4>
                        <div className="flex items-center gap-2">
                          {advancedDirty ? <PendingSaveBadge /> : null}
                          <DirtySaveButton
                            dirty={advancedDirty}
                            saving={saveSubscription.isPending}
                            onClick={() => void saveAdvancedSettings()}
                          />
                        </div>
                      </div>

                      <div className="-mt-1 space-y-2">
                        <Label>{t("siteConfig.contentSubscriptionAllowedTypes")}</Label>
                        <div className="grid grid-cols-4 gap-2">
                          {SUBSCRIPTION_CONTENT_OPTIONS.map((option) => {
                            const checked = advancedForm.allowed_content_types.includes(option.key);
                            return (
                              <button
                                key={option.key}
                                type="button"
                                onClick={() => toggleAllowedContentType(option.key)}
                                className={`w-full rounded-[var(--admin-radius-md)] border px-1 py-1.5 text-sm transition ${
                                  checked
                                    ? "border-[rgb(var(--admin-accent-rgb)/0.28)] bg-[rgb(var(--admin-accent-rgb)/0.12)] text-foreground"
                                    : "border-border/70 bg-background/40 text-muted-foreground hover:text-foreground"
                                }`}
                              >
                                <span className="font-medium leading-none">{option.label}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="subscription-subject-template">
                          {t("siteConfig.contentSubscriptionSubjectTemplate")}
                        </Label>
                        <Input
                          id="subscription-subject-template"
                          value={advancedForm.mail_subject_template}
                          onChange={(event) =>
                            setAdvancedForm((current) => ({
                              ...current,
                              mail_subject_template: event.target.value,
                            }))
                          }
                          className={SUBSCRIPTION_TEMPLATE_FIELD_CLASS}
                          placeholder={DEFAULT_SUBSCRIPTION_SUBJECT_TEMPLATE}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="subscription-body-template">
                          {t("siteConfig.contentSubscriptionBodyTemplate")}
                        </Label>
                        <Textarea
                          id="subscription-body-template"
                          rows={8}
                          value={advancedForm.mail_body_template}
                          onChange={(event) =>
                            setAdvancedForm((current) => ({
                              ...current,
                              mail_body_template: event.target.value,
                            }))
                          }
                          className={SUBSCRIPTION_TEMPLATE_FIELD_CLASS}
                          placeholder={DEFAULT_SUBSCRIPTION_BODY_TEMPLATE}
                        />
                        <div className="flex justify-start pt-1">
                          <LabelWithHelp
                            className="gap-1.5"
                            label={
                              <span className="text-xs font-medium text-muted-foreground">
                                {t("siteConfig.contentSubscriptionPlaceholderHelpLabel")}
                              </span>
                            }
                            title={t("siteConfig.contentSubscriptionPlaceholderHelpTitle")}
                            description={t(
                              "siteConfig.contentSubscriptionPlaceholderHelpDescription",
                            )}
                            usageTitle={t("siteConfig.contentSubscriptionPlaceholderHelpUsageTitle")}
                            usageItems={[
                              t("siteConfig.contentSubscriptionPlaceholderHelpSiteName"),
                              t("siteConfig.contentSubscriptionPlaceholderHelpContentType"),
                              t("siteConfig.contentSubscriptionPlaceholderHelpContentTypeLabel"),
                              t("siteConfig.contentSubscriptionPlaceholderHelpContentTitle"),
                              t("siteConfig.contentSubscriptionPlaceholderHelpContentSummary"),
                              t("siteConfig.contentSubscriptionPlaceholderHelpContentUrl"),
                              t("siteConfig.contentSubscriptionPlaceholderHelpFeedUrl"),
                            ]}
                          />
                        </div>
                      </div>

                    </div>
                  ) : null
                }
              disabled={saveSubscription.isPending}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
