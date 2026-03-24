import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGet,
  useUpdateCommunityConfigApiV1AdminSiteConfigCommunityConfigPut,
  getGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGetQueryKey,
} from "@/api/generated/admin/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { HintBanner } from "@/components/ui/HintBanner";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { Save } from "lucide-react";
import {
  createCommunityForm,
  communityFormToUpdate,
} from "@/lib/community-config";
import { useI18n } from "@/i18n";
import {
  LOGIN_MODE_OPTIONS,
  AVATAR_STRATEGY_OPTIONS,
  MIGRATION_STATE_OPTIONS,
  LOGIN_MODE_LABELS,
  AVATAR_STRATEGY_LABELS,
  MIGRATION_STATE_LABELS,
  MODERATION_MODE_LABELS,
  DEFAULT_SORTING_LABELS,
  GUEST_AVATAR_MODE_LABELS,
  optionLabel,
} from "../constants";

const MODERATION_MODE_OPTIONS = ["all_pending", "manual", "mixed"] as const;
const DEFAULT_SORTING_OPTIONS = ["latest", "oldest", "hottest"] as const;
const GUEST_AVATAR_MODE_OPTIONS = ["preset", "identicon", "gravatar"] as const;

export function CommunityTab() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const { data: resp, isLoading } = useGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGet();
  const config = resp?.data;
  const [form, setForm] = useState(() => createCommunityForm());
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (config) {
      setForm(createCommunityForm(config));
      setFormError("");
    }
  }, [config]);

  const save = useUpdateCommunityConfigApiV1AdminSiteConfigCommunityConfigPut({
    mutation: {
      onMutate: () => {
        setFormError("");
      },
      onSuccess: (saved) => {
        queryClient.invalidateQueries({ queryKey: getGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGetQueryKey() });
        setForm(createCommunityForm(saved.data));
      },
      onError: (error) => {
        setFormError(
          error instanceof Error
            ? error.message
            : t("siteConfig.commentSaveError"),
        );
      },
    },
  });

  if (isLoading && !config) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  const updateField = <K extends keyof typeof form>(
    key: K,
    value: (typeof form)[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Card className="mt-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">
          {t("siteConfig.community")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("siteConfig.communityDescription")}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* ── Basic Settings ── */}
        <HintBanner>{t("siteConfig.communityBasicHint")}</HintBanner>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label>{t("siteConfig.commentProvider")}</Label>
            <Input value={form.provider} disabled />
          </div>
          <div className="space-y-1">
            <Label>{t("siteConfig.commentServerUrl")}</Label>
            <Input
              value={form.server_url}
              onChange={(e) => updateField("server_url", e.target.value)}
              placeholder="https://waline.example.com"
            />
          </div>
          <div className="space-y-1">
            <Label>{t("siteConfig.commentLoginMode")}</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.login_mode}
              onChange={(e) => updateField("login_mode", e.target.value)}
            >
              {LOGIN_MODE_OPTIONS.map((v) => (
                <option key={v} value={v}>
                  {optionLabel(LOGIN_MODE_LABELS, v, lang)}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.anonymous_enabled}
              onChange={(e) =>
                updateField("anonymous_enabled", e.target.checked)
              }
              className="h-4 w-4 rounded border-border"
            />
            <span>{t("siteConfig.commentAnonymousEnabled")}</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.image_uploader}
              onChange={(e) => updateField("image_uploader", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            <span>{t("siteConfig.commentImageUploader")}</span>
          </label>
        </div>

        {/* ── Display Settings ── */}
        <div className="rounded-lg border p-4 space-y-4">
          <h3 className="text-sm font-semibold">
            {t("siteConfig.displaySettings")}
          </h3>
          <HintBanner>{t("siteConfig.communityDisplayHint")}</HintBanner>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>{t("siteConfig.commentDefaultSorting")}</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.default_sorting}
                onChange={(e) => updateField("default_sorting", e.target.value)}
              >
                {DEFAULT_SORTING_OPTIONS.map((v) => (
                  <option key={v} value={v}>
                    {optionLabel(DEFAULT_SORTING_LABELS, v, lang)}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label>{t("siteConfig.commentModerationMode")}</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.moderation_mode}
                onChange={(e) => updateField("moderation_mode", e.target.value)}
              >
                {MODERATION_MODE_OPTIONS.map((v) => (
                  <option key={v} value={v}>
                    {optionLabel(MODERATION_MODE_LABELS, v, lang)}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label>{t("siteConfig.commentPageSize")}</Label>
              <Input
                type="number"
                min={1}
                value={form.page_size}
                onChange={(e) => updateField("page_size", e.target.value)}
                placeholder="20"
              />
            </div>
            <div className="space-y-1">
              <Label>{t("siteConfig.commentEmojiPresets")}</Label>
              <Input
                value={form.emoji_presets}
                onChange={(e) => updateField("emoji_presets", e.target.value)}
                placeholder="apple, weibo, qq, bilibili, twemoji, github"
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.enable_enjoy_search}
                onChange={(e) =>
                  updateField("enable_enjoy_search", e.target.checked)
                }
                className="h-4 w-4 rounded border-border"
              />
              <span>{t("siteConfig.commentEnableEnjoySearch")}</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.draft_enabled}
                onChange={(e) => updateField("draft_enabled", e.target.checked)}
                className="h-4 w-4 rounded border-border"
              />
              <span>{t("siteConfig.commentDraftEnabled")}</span>
            </label>
          </div>
        </div>

        {/* ── Advanced Settings ── */}
        <CollapsibleSection
          title={t("siteConfig.advancedSettings")}
          defaultOpen={false}
        >
          <div className="space-y-4">
            <HintBanner>{t("siteConfig.advancedSettingsHint")}</HintBanner>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>{t("siteConfig.commentMigrationState")}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.migration_state}
                  onChange={(e) =>
                    updateField("migration_state", e.target.value)
                  }
                >
                  {MIGRATION_STATE_OPTIONS.map((v) => (
                    <option key={v} value={v}>
                      {optionLabel(MIGRATION_STATE_LABELS, v, lang)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.commentAvatarStrategy")}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.avatar_strategy}
                  onChange={(e) =>
                    updateField("avatar_strategy", e.target.value)
                  }
                >
                  {AVATAR_STRATEGY_OPTIONS.map((v) => (
                    <option key={v} value={v}>
                      {optionLabel(AVATAR_STRATEGY_LABELS, v, lang)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.commentGuestAvatarMode")}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.guest_avatar_mode}
                  onChange={(e) =>
                    updateField("guest_avatar_mode", e.target.value)
                  }
                >
                  {GUEST_AVATAR_MODE_OPTIONS.map((v) => (
                    <option key={v} value={v}>
                      {optionLabel(GUEST_AVATAR_MODE_LABELS, v, lang)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <Label>{t("siteConfig.commentAvatarPresets")}</Label>
              <Textarea
                value={form.avatar_presets}
                onChange={(e) => updateField("avatar_presets", e.target.value)}
                rows={8}
                placeholder='[{"key":"shiro","label":"Shiro","avatar_url":"https://..."}]'
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>
                  {t("siteConfig.commentOauthUrl")} ({t("common.optional")})
                </Label>
                <Input
                  value={form.oauth_url}
                  onChange={(e) => updateField("oauth_url", e.target.value)}
                  placeholder="https://accounts.google.com/..."
                />
              </div>
              <div className="space-y-1">
                <Label>
                  {t("siteConfig.commentOauthProviders")} (
                  {t("common.optional")})
                </Label>
                <Input
                  value={form.oauth_providers}
                  onChange={(e) =>
                    updateField("oauth_providers", e.target.value)
                  }
                  placeholder="github, google"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label>{t("siteConfig.commentSurfaces")}</Label>
              <Textarea
                value={form.surfaces}
                onChange={(e) => updateField("surfaces", e.target.value)}
                rows={8}
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                {t("siteConfig.commentSurfacesHint")}
              </p>
            </div>

            <div className="space-y-1">
              <Label>
                {t("siteConfig.commentHelperCopy")} ({t("common.optional")})
              </Label>
              <Textarea
                value={form.helper_copy}
                onChange={(e) => updateField("helper_copy", e.target.value)}
                rows={4}
                placeholder={t("siteConfig.commentHelperHint")}
              />
              <p className="text-xs text-muted-foreground">
                {t("siteConfig.commentHelperHint")}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>
                  {t("siteConfig.commentMeta")} ({t("common.optional")})
                </Label>
                <Input
                  value={form.meta}
                  onChange={(e) => updateField("meta", e.target.value)}
                  placeholder="nick, mail"
                />
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.commentRequiredMeta")}</Label>
                <Input
                  value={form.required_meta}
                  onChange={(e) => updateField("required_meta", e.target.value)}
                  placeholder="nick"
                />
              </div>
            </div>
          </div>
        </CollapsibleSection>

        {formError && <p className="text-sm text-destructive">{formError}</p>}

        <Button onClick={() => save.mutate({ data: communityFormToUpdate(form) })} disabled={save.isPending}>
          <Save className="h-4 w-4 mr-2" />
          {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}
