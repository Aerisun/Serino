import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { CommunityConfigAdminRead } from "@serino/api-client/models";
import {
  useGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGet,
  useUpdateCommunityConfigApiV1AdminSiteConfigCommunityConfigPut,
  getGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGetQueryKey,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent } from "@/components/ui/Card";
import { HintBanner } from "@/components/ui/HintBanner";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Loader2, Save, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ResourceUploadField } from "@/components/ResourceUploadField";
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
  const { data: resp, isLoading } =
    useGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGet();
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
        queryClient.invalidateQueries({
          queryKey:
            getGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGetQueryKey(),
        });
        toast.success(t("common.operationSuccess"));
        if (saved.data && "provider" in saved.data) {
          setForm(createCommunityForm(saved.data as CommunityConfigAdminRead));
        }
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

  const updateAvatarPreset = (
    index: number,
    key: "key" | "label" | "avatar_url" | "note",
    value: string,
  ) => {
    updateField(
      "avatar_presets",
      form.avatar_presets.map((item, currentIndex) =>
        currentIndex === index ? { ...item, [key]: value } : item,
      ),
    );
  };

  const addAvatarPreset = () => {
    updateField("avatar_presets", [
      ...form.avatar_presets,
      { key: "", label: "", avatar_url: "", note: "" },
    ]);
  };

  const removeAvatarPreset = (index: number) => {
    updateField(
      "avatar_presets",
      form.avatar_presets.filter((_, currentIndex) => currentIndex !== index),
    );
  };

  return (
    <Card className="mt-4">
      <CardContent className="space-y-6 pt-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label>{t("siteConfig.commentLoginMode")}</Label>
            <Select
              value={form.login_mode}
              onValueChange={(value) => updateField("login_mode", value)}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("siteConfig.commentLoginMode")} />
              </SelectTrigger>
              <SelectContent>
                {LOGIN_MODE_OPTIONS.map((v) => (
                  <SelectItem key={v} value={v}>
                    {optionLabel(LOGIN_MODE_LABELS, v, lang)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label>{t("siteConfig.commentDefaultSorting")}</Label>
            <Select
              value={form.default_sorting}
              onValueChange={(value) => updateField("default_sorting", value)}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={t("siteConfig.commentDefaultSorting")}
                />
              </SelectTrigger>
              <SelectContent>
                {DEFAULT_SORTING_OPTIONS.map((v) => (
                  <SelectItem key={v} value={v}>
                    {optionLabel(DEFAULT_SORTING_LABELS, v, lang)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label>{t("siteConfig.commentModerationMode")}</Label>
            <Select
              value={form.moderation_mode}
              onValueChange={(value) => updateField("moderation_mode", value)}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={t("siteConfig.commentModerationMode")}
                />
              </SelectTrigger>
              <SelectContent>
                {MODERATION_MODE_OPTIONS.map((v) => (
                  <SelectItem key={v} value={v}>
                    {optionLabel(MODERATION_MODE_LABELS, v, lang)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
        </div>

        <div className="grid gap-3">
          <AppleSwitch
            checked={form.anonymous_enabled}
            onCheckedChange={(checked) =>
              updateField("anonymous_enabled", checked)
            }
            label={t("siteConfig.commentAnonymousEnabled")}
            description={t("siteConfig.commentAnonymousEnabledDesc")}
          />
          <AppleSwitch
            checked={form.image_uploader}
            onCheckedChange={(checked) =>
              updateField("image_uploader", checked)
            }
            label={t("siteConfig.commentImageUploader")}
            description={t("siteConfig.commentImageUploaderDesc")}
          />
          <AppleSwitch
            checked={form.enable_enjoy_search}
            onCheckedChange={(checked) =>
              updateField("enable_enjoy_search", checked)
            }
            label={t("siteConfig.commentEnableEnjoySearch")}
            description={t("siteConfig.commentEnableEnjoySearchDesc")}
          />
        </div>

        <CollapsibleSection
          title={t("siteConfig.advancedSettings")}
          defaultOpen={false}
        >
          <div className="space-y-4">
            <HintBanner>{t("siteConfig.advancedSettingsHint")}</HintBanner>

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
                  placeholder="http://localhost:8360"
                />
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.commentMigrationState")}</Label>
                <Select
                  value={form.migration_state}
                  onValueChange={(value) =>
                    updateField("migration_state", value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={t("siteConfig.commentMigrationState")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {MIGRATION_STATE_OPTIONS.map((v) => (
                      <SelectItem key={v} value={v}>
                        {optionLabel(MIGRATION_STATE_LABELS, v, lang)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.commentAvatarStrategy")}</Label>
                <Select
                  value={form.avatar_strategy}
                  onValueChange={(value) =>
                    updateField("avatar_strategy", value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={t("siteConfig.commentAvatarStrategy")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {AVATAR_STRATEGY_OPTIONS.map((v) => (
                      <SelectItem key={v} value={v}>
                        {optionLabel(AVATAR_STRATEGY_LABELS, v, lang)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.commentGuestAvatarMode")}</Label>
                <Select
                  value={form.guest_avatar_mode}
                  onValueChange={(value) =>
                    updateField("guest_avatar_mode", value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={t("siteConfig.commentGuestAvatarMode")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {GUEST_AVATAR_MODE_OPTIONS.map((v) => (
                      <SelectItem key={v} value={v}>
                        {optionLabel(GUEST_AVATAR_MODE_LABELS, v, lang)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1">
              <Label>{t("siteConfig.commentEmojiPresets")}</Label>
              <Input
                value={form.emoji_presets}
                onChange={(e) => updateField("emoji_presets", e.target.value)}
                placeholder="twemoji, qq, bilibili"
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <Label>{t("siteConfig.commentAvatarPresets")}</Label>
                <Button type="button" variant="outline" size="sm" onClick={addAvatarPreset}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t("common.add")}
                </Button>
              </div>
              <div className="space-y-3">
                {form.avatar_presets.map((preset, index) => (
                  <Card key={`${preset.key || "preset"}-${index}`} className="border-dashed border-border/70 bg-background/40">
                    <CardContent className="grid gap-3 p-4">
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-1">
                          <Label>{t("common.name")}</Label>
                          <Input
                            value={preset.label}
                            onChange={(e) => updateAvatarPreset(index, "label", e.target.value)}
                            placeholder="Shiro"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label>{t("siteConfig.iconKey")}</Label>
                          <Input
                            value={preset.key}
                            onChange={(e) => updateAvatarPreset(index, "key", e.target.value)}
                            placeholder="shiro"
                          />
                        </div>
                      </div>
                      <ResourceUploadField
                        label={t("friends.avatarUrl")}
                        value={preset.avatar_url}
                        category="community-avatar"
                        scope="system"
                        accept="image/*"
                        placeholder="/media/internal/assets/..."
                        note={preset.note ?? `${preset.label || preset.key || "社区默认头像"}（社区头像预设）`}
                        onChange={(value) => updateAvatarPreset(index, "avatar_url", value)}
                      />
                      <div className="space-y-1">
                        <Label>{t("assets.note")}</Label>
                        <Input
                          value={preset.note ?? ""}
                          onChange={(e) => updateAvatarPreset(index, "note", e.target.value)}
                          placeholder={t("assets.note")}
                        />
                      </div>
                      <div className="flex justify-end">
                        <Button type="button" variant="destructive" size="sm" onClick={() => removeAvatarPreset(index)}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          {t("common.delete")}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            <HintBanner>
              Google / GitHub 访客认证已经移到“审核 &gt; 访客”页面集中管理，这里只保留评论系统自身的配置。
            </HintBanner>

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

        <Button
          onClick={() => save.mutate({ data: communityFormToUpdate(form) })}
          disabled={save.isPending}
          className="inline-flex shadow-[0_14px_30px_-16px_rgb(var(--shiro-accent-rgb)/0.42)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_36px_-16px_rgb(var(--shiro-accent-rgb)/0.5)] active:translate-y-0 active:scale-[0.98]"
        >
          {save.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}
