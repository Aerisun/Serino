import { useEffect, useId, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight, RotateCcw } from "lucide-react";
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
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { cn } from "@/lib/utils";

const FEATURE_FLAGS = ["toc", "reading_progress", "diary_private_enabled"] as const;
const OWNER_COMMENT_ACTIVITY_CONTENT_TYPES_FLAG =
  "recent_activity_owner_comment_content_types";
const OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS = [
  { key: "posts", labelKey: "nav.posts" },
  { key: "diary", labelKey: "nav.diary" },
  { key: "thoughts", labelKey: "nav.thoughts" },
  { key: "excerpts", labelKey: "nav.excerpts" },
] as const;
const SUBSCRIPTION_CONTENT_OPTIONS = [
  { key: "posts", label: "文章" },
  { key: "diary", label: "日记" },
  { key: "thoughts", label: "碎碎念" },
  { key: "excerpts", label: "文摘" },
] as const;
const DEFAULT_SUBSCRIPTION_SUBJECT_TEMPLATE = "[{site_name}] {content_title}";
const DEFAULT_SUBSCRIPTION_BODY_TEMPLATE =
  "{site_name} 有新的{content_type_label}内容发布。\n\n{content_title}\n{content_summary}\n\n阅读链接：{content_url}\nRSS：{feed_url}";
const DEFAULT_COMMENT_FEEDBACK_SUBJECT_TEMPLATE = "[{site_name}] {reply_author_name} 回复了你的评论";
const DEFAULT_COMMENT_FEEDBACK_BODY_TEMPLATE =
  "{reply_author_name} 回复了你在 {site_name} 的评论。\n\n你的评论：\n{parent_comment}\n\n回复内容：\n{reply_content}\n\n查看回复：{comment_url}";
const SUBSCRIPTION_TEMPLATE_FIELD_CLASS =
  "mx-px w-[calc(100%-2px)] max-w-full border-border/70 bg-background/72 shadow-none [backdrop-filter:none] [-webkit-backdrop-filter:none] focus:!border-[rgb(var(--admin-accent-rgb)/0.36)] focus:shadow-none focus-visible:!ring-[rgb(var(--admin-accent-rgb)/0.26)] focus-visible:!ring-offset-0";

type SubscriptionContentType = (typeof SUBSCRIPTION_CONTENT_OPTIONS)[number]["key"];
type OwnerCommentActivityContentType =
  (typeof OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS)[number]["key"];
type FeatureFlags = Record<string, unknown>;

interface AdvancedSubscriptionForm {
  allowed_content_types: SubscriptionContentType[];
  mail_subject_template: string;
  mail_body_template: string;
}

interface CommentFeedbackForm {
  comment_feedback_subject_template: string;
  comment_feedback_body_template: string;
}

type SubscriptionConfigWithAdvanced = {
  enabled?: boolean;
  smtp_test_passed?: boolean;
  allowed_content_types?: string[];
  mail_subject_template?: string;
  mail_body_template?: string;
  comment_feedback_enabled?: boolean;
  comment_feedback_subject_template?: string;
  comment_feedback_body_template?: string;
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

function createCommentFeedbackForm(
  config?: SubscriptionConfigWithAdvanced,
): CommentFeedbackForm {
  return {
    comment_feedback_subject_template:
      config?.comment_feedback_subject_template?.trim() ||
      DEFAULT_COMMENT_FEEDBACK_SUBJECT_TEMPLATE,
    comment_feedback_body_template:
      config?.comment_feedback_body_template?.trim() ||
      DEFAULT_COMMENT_FEEDBACK_BODY_TEMPLATE,
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

function isSameCommentFeedbackForm(
  left: CommentFeedbackForm,
  right: CommentFeedbackForm,
): boolean {
  return (
    left.comment_feedback_subject_template === right.comment_feedback_subject_template &&
    left.comment_feedback_body_template === right.comment_feedback_body_template
  );
}

function createOwnerCommentActivityContentTypes(
  featureFlags?: FeatureFlags,
): OwnerCommentActivityContentType[] {
  const stored = featureFlags?.[OWNER_COMMENT_ACTIVITY_CONTENT_TYPES_FLAG];
  if (!Array.isArray(stored)) {
    return OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS.map((option) => option.key);
  }

  const selected = new Set(
    stored.filter(
      (item): item is OwnerCommentActivityContentType =>
        typeof item === "string" &&
        OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS.some((option) => option.key === item),
    ),
  );
  return OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS
    .map((option) => option.key)
    .filter((key) => selected.has(key));
}

function isSameOwnerCommentActivityContentTypes(
  left: OwnerCommentActivityContentType[],
  right: OwnerCommentActivityContentType[],
): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
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
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>({});
  const [subscriptionEnabled, setSubscriptionEnabled] = useState(false);
  const [commentFeedbackEnabled, setCommentFeedbackEnabled] = useState(false);
  const [advancedForm, setAdvancedForm] = useState<AdvancedSubscriptionForm>(() =>
    createAdvancedSubscriptionForm(),
  );
  const [savedAdvancedForm, setSavedAdvancedForm] =
    useState<AdvancedSubscriptionForm>(() => createAdvancedSubscriptionForm());
  const [commentFeedbackForm, setCommentFeedbackForm] =
    useState<CommentFeedbackForm>(() => createCommentFeedbackForm());
  const [savedCommentFeedbackForm, setSavedCommentFeedbackForm] =
    useState<CommentFeedbackForm>(() => createCommentFeedbackForm());
  const [advancedExpanded, setAdvancedExpanded] = useState(false);
  const [commentFeedbackExpanded, setCommentFeedbackExpanded] = useState(false);
  const [ownerCommentActivityExpanded, setOwnerCommentActivityExpanded] = useState(false);
  const ownerCommentActivityContentId = useId();
  const [ownerCommentActivityContentTypes, setOwnerCommentActivityContentTypes] = useState<
    OwnerCommentActivityContentType[]
  >(() => createOwnerCommentActivityContentTypes());
  const [savedOwnerCommentActivityContentTypes, setSavedOwnerCommentActivityContentTypes] = useState<
    OwnerCommentActivityContentType[]
  >(() => createOwnerCommentActivityContentTypes());

  useEffect(() => {
    if (profile) {
      const nextFeatureFlags = (profile.feature_flags ?? {}) as FeatureFlags;
      setFeatureFlags(nextFeatureFlags);
      const nextOwnerCommentActivityContentTypes =
        createOwnerCommentActivityContentTypes(nextFeatureFlags);
      setOwnerCommentActivityContentTypes(nextOwnerCommentActivityContentTypes);
      setSavedOwnerCommentActivityContentTypes(nextOwnerCommentActivityContentTypes);
    }
  }, [profile]);

  useEffect(() => {
    if (subscriptionConfig) {
      setSubscriptionEnabled(Boolean(subscriptionConfig.enabled));
      setCommentFeedbackEnabled(Boolean(subscriptionConfig.comment_feedback_enabled));
      const nextForm = createAdvancedSubscriptionForm(subscriptionConfig);
      setAdvancedForm(nextForm);
      setSavedAdvancedForm(nextForm);
      const nextFeedbackForm = createCommentFeedbackForm(subscriptionConfig);
      setCommentFeedbackForm(nextFeedbackForm);
      setSavedCommentFeedbackForm(nextFeedbackForm);
    }
  }, [subscriptionConfig]);

  useEffect(() => {
    if (!(smtpTestPassed && subscriptionEnabled)) {
      setAdvancedExpanded(false);
    }
  }, [smtpTestPassed, subscriptionEnabled]);

  useEffect(() => {
    if (!commentFeedbackEnabled) {
      setCommentFeedbackExpanded(false);
    }
  }, [commentFeedbackEnabled]);

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
        acc[key] = typeof featureFlags[key] === "boolean" ? Boolean(featureFlags[key]) : true;
        return acc;
      }, {}),
    [featureFlags],
  );

  if (isLoading || subscriptionLoading) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  const personalizationFlags = [
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

  const buildSaveData = (nextFeatureFlags: FeatureFlags) => ({
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

  const toggleOwnerCommentActivityContentType = (
    contentType: OwnerCommentActivityContentType,
  ) => {
    setOwnerCommentActivityContentTypes((current) => {
      const selected = current.includes(contentType)
        ? current.filter((item) => item !== contentType)
        : [...current, contentType];
      return OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS
        .map((option) => option.key)
        .filter((key) => selected.includes(key));
    });
  };

  const saveOwnerCommentActivitySettings = async () => {
    const previousFlags = featureFlags;
    const nextFeatureFlags = {
      ...featureFlags,
      [OWNER_COMMENT_ACTIVITY_CONTENT_TYPES_FLAG]: ownerCommentActivityContentTypes,
    };
    setFeatureFlags(nextFeatureFlags);

    try {
      await saveProfile.mutateAsync({ data: buildSaveData(nextFeatureFlags) });
      setSavedOwnerCommentActivityContentTypes(ownerCommentActivityContentTypes);
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

  const handleCommentFeedbackToggle = async (nextEnabled: boolean) => {
    const previousEnabled = commentFeedbackEnabled;
    setCommentFeedbackEnabled(nextEnabled);

    try {
      await saveSubscription.mutateAsync({ data: { comment_feedback_enabled: nextEnabled } as any });
      if (nextEnabled && !smtpTestPassed) {
        toast.warning(t("siteConfig.commentFeedbackServiceNotConfigured"));
      }
    } catch {
      setCommentFeedbackEnabled(previousEnabled);
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

  const restoreAdvancedDefaults = () => {
    setAdvancedForm(createAdvancedSubscriptionForm());
  };

  const restoreCommentFeedbackDefaults = () => {
    setCommentFeedbackForm(createCommentFeedbackForm());
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

  const saveCommentFeedbackSettings = async () => {
    try {
      await saveSubscription.mutateAsync({ data: commentFeedbackForm as any });
      setSavedCommentFeedbackForm(commentFeedbackForm);
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
  const commentFeedbackDirty = !isSameCommentFeedbackForm(commentFeedbackForm, savedCommentFeedbackForm);
  const ownerCommentActivityDirty = !isSameOwnerCommentActivityContentTypes(
    ownerCommentActivityContentTypes,
    savedOwnerCommentActivityContentTypes,
  );
  const canExpandAdvanced = smtpTestPassed && subscriptionEnabled;
  const canExpandCommentFeedback = commentFeedbackEnabled;
  const commentFeedbackDescription = smtpTestPassed
    ? t("siteConfig.commentFeedbackConfigHint")
    : t("siteConfig.commentFeedbackSetupGuide");

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
            <AppleSwitch
              checked={resolvedFeatureFlags.diary_private_enabled}
              onCheckedChange={() => void handleFeatureToggle("diary_private_enabled")}
              label={t("siteConfig.featureDiaryPrivate")}
              description={t("siteConfig.featureDiaryPrivateDesc")}
              disabled={saveProfile.isPending}
            />

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
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          {advancedDirty ? <PendingSaveBadge /> : null}
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="gap-2"
                            onClick={restoreAdvancedDefaults}
                            disabled={saveSubscription.isPending}
                          >
                            <RotateCcw className="h-4 w-4" />
                            {t("siteConfig.mailTemplateRestoreDefault")}
                          </Button>
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

            <AppleSwitch
              checked={commentFeedbackEnabled}
              onCheckedChange={(checked) => void handleCommentFeedbackToggle(checked)}
              switchLeading={
                canExpandCommentFeedback ? (
                  <button
                    type="button"
                    aria-label={commentFeedbackExpanded ? t("common.collapse") : t("common.expand")}
                    aria-expanded={commentFeedbackExpanded}
                    disabled={saveSubscription.isPending}
                    onClick={() => setCommentFeedbackExpanded((current) => !current)}
                    className={cn(
                      "inline-flex h-6 w-6 items-center justify-center rounded-md border border-border/70 bg-background/40 text-muted-foreground transition hover:bg-background/70 hover:text-foreground",
                      saveSubscription.isPending && "cursor-not-allowed opacity-60",
                      commentFeedbackExpanded && "text-foreground",
                    )}
                  >
                    <ChevronRight
                      className={cn(
                        "h-4 w-4 transition-transform duration-200",
                        commentFeedbackExpanded && "rotate-90",
                      )}
                    />
                  </button>
                ) : null
              }
              label={t("siteConfig.commentFeedbackEnabled")}
              description={commentFeedbackDescription}
              descriptionClassName={
                smtpTestPassed ? undefined : "text-amber-600 dark:text-amber-300"
              }
              expandableOpen={canExpandCommentFeedback && commentFeedbackExpanded}
              expandableContent={
                canExpandCommentFeedback ? (
                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="text-sm font-semibold">
                        {t("siteConfig.commentFeedbackAdvancedTitle")}
                      </h4>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {commentFeedbackDirty ? <PendingSaveBadge /> : null}
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="gap-2"
                          onClick={restoreCommentFeedbackDefaults}
                          disabled={saveSubscription.isPending}
                        >
                          <RotateCcw className="h-4 w-4" />
                          {t("siteConfig.mailTemplateRestoreDefault")}
                        </Button>
                        <DirtySaveButton
                          dirty={commentFeedbackDirty}
                          saving={saveSubscription.isPending}
                          onClick={() => void saveCommentFeedbackSettings()}
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="comment-feedback-subject-template">
                        {t("siteConfig.commentFeedbackSubjectTemplate")}
                      </Label>
                      <Input
                        id="comment-feedback-subject-template"
                        value={commentFeedbackForm.comment_feedback_subject_template}
                        onChange={(event) =>
                          setCommentFeedbackForm((current) => ({
                            ...current,
                            comment_feedback_subject_template: event.target.value,
                          }))
                        }
                        className={SUBSCRIPTION_TEMPLATE_FIELD_CLASS}
                        placeholder={DEFAULT_COMMENT_FEEDBACK_SUBJECT_TEMPLATE}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="comment-feedback-body-template">
                        {t("siteConfig.commentFeedbackBodyTemplate")}
                      </Label>
                      <Textarea
                        id="comment-feedback-body-template"
                        rows={8}
                        value={commentFeedbackForm.comment_feedback_body_template}
                        onChange={(event) =>
                          setCommentFeedbackForm((current) => ({
                            ...current,
                            comment_feedback_body_template: event.target.value,
                          }))
                        }
                        className={SUBSCRIPTION_TEMPLATE_FIELD_CLASS}
                        placeholder={DEFAULT_COMMENT_FEEDBACK_BODY_TEMPLATE}
                      />
                      <div className="flex justify-start pt-1">
                        <LabelWithHelp
                          className="gap-1.5"
                          label={
                            <span className="text-xs font-medium text-muted-foreground">
                              {t("siteConfig.commentFeedbackPlaceholderHelpLabel")}
                            </span>
                          }
                          title={t("siteConfig.commentFeedbackPlaceholderHelpTitle")}
                          description={t("siteConfig.commentFeedbackPlaceholderHelpDescription")}
                          usageTitle={t("siteConfig.commentFeedbackPlaceholderHelpUsageTitle")}
                          usageItems={[
                            t("siteConfig.commentFeedbackPlaceholderHelpSiteName"),
                            t("siteConfig.commentFeedbackPlaceholderHelpContentType"),
                            t("siteConfig.commentFeedbackPlaceholderHelpContentSlug"),
                            t("siteConfig.commentFeedbackPlaceholderHelpContentPath"),
                            t("siteConfig.commentFeedbackPlaceholderHelpParentAuthor"),
                            t("siteConfig.commentFeedbackPlaceholderHelpParentComment"),
                            t("siteConfig.commentFeedbackPlaceholderHelpReplyAuthor"),
                            t("siteConfig.commentFeedbackPlaceholderHelpReplyContent"),
                            t("siteConfig.commentFeedbackPlaceholderHelpCommentUrl"),
                          ]}
                        />
                      </div>
                    </div>
                  </div>
                ) : null
              }
              disabled={saveSubscription.isPending}
            />

            <CollapsibleSection title={t("siteConfig.personalization")}>
              <div className="space-y-4">
                {personalizationFlags.map((flag) => (
                  <AppleSwitch
                    key={flag.key}
                    checked={resolvedFeatureFlags[flag.key]}
                    onCheckedChange={() => void handleFeatureToggle(flag.key)}
                    label={flag.label}
                    description={flag.desc}
                    disabled={saveProfile.isPending}
                  />
                ))}

                <div className="rounded-[var(--admin-radius-lg)] admin-glass px-4 py-3 shadow-[var(--admin-shadow-sm)]">
                  <div className="flex items-start justify-between gap-4">
                    <LabelWithHelp
                      className="min-w-0 gap-1.5"
                      label={
                        <span className="text-sm font-medium tracking-tight text-foreground/92">
                          {t("siteConfig.recentActivityOwnerComment")}
                        </span>
                      }
                      title={t("siteConfig.recentActivityOwnerComment")}
                      description={t("siteConfig.recentActivityOwnerCommentHelp")}
                    />
                    <button
                      type="button"
                      aria-label={
                        ownerCommentActivityExpanded ? t("common.collapse") : t("common.expand")
                      }
                      aria-controls={ownerCommentActivityContentId}
                      aria-expanded={ownerCommentActivityExpanded}
                      onClick={() => setOwnerCommentActivityExpanded((current) => !current)}
                      className={cn(
                        "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-border/70 bg-background/40 text-muted-foreground transition hover:bg-background/70 hover:text-foreground",
                        ownerCommentActivityExpanded && "text-foreground",
                      )}
                    >
                      <ChevronRight
                        className={cn(
                          "h-4 w-4 transition-transform duration-200",
                          ownerCommentActivityExpanded && "rotate-90",
                        )}
                      />
                    </button>
                  </div>

                  <div
                    id={ownerCommentActivityContentId}
                    aria-hidden={!ownerCommentActivityExpanded}
                    inert={!ownerCommentActivityExpanded ? true : undefined}
                    className={cn(
                      "overflow-hidden transition-[max-height,opacity,margin,padding] duration-200 ease-in-out",
                      ownerCommentActivityExpanded
                        ? "mt-3 max-h-80 border-t border-border/60 pt-3 opacity-100"
                        : "max-h-0 opacity-0",
                    )}
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <Label>{t("siteConfig.recentActivityOwnerCommentTypes")}</Label>
                        <div className="flex items-center gap-2">
                          {ownerCommentActivityDirty ? <PendingSaveBadge /> : null}
                          <DirtySaveButton
                            dirty={ownerCommentActivityDirty}
                            saving={saveProfile.isPending}
                            onClick={() => void saveOwnerCommentActivitySettings()}
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        {OWNER_COMMENT_ACTIVITY_CONTENT_TYPE_OPTIONS.map((option) => {
                          const checked = ownerCommentActivityContentTypes.includes(option.key);
                          return (
                            <button
                              key={option.key}
                              type="button"
                              onClick={() => toggleOwnerCommentActivityContentType(option.key)}
                              disabled={saveProfile.isPending}
                              className={cn(
                                "w-full rounded-[var(--admin-radius-md)] border px-2 py-2 text-sm font-medium transition",
                                checked
                                  ? "border-[rgb(var(--admin-accent-rgb)/0.28)] bg-[rgb(var(--admin-accent-rgb)/0.12)] text-foreground"
                                  : "border-border/70 bg-background/40 text-muted-foreground hover:text-foreground",
                                saveProfile.isPending && "cursor-not-allowed opacity-60",
                              )}
                            >
                              {t(option.labelKey)}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CollapsibleSection>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
