import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCommunityConfig, updateCommunityConfig } from "@/api/endpoints/site-config";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Save } from "lucide-react";
import { createCommunityForm, communityFormToUpdate } from "@/lib/community-config";
import { useI18n } from "@/i18n";
import { LOGIN_MODE_OPTIONS, AVATAR_STRATEGY_OPTIONS, MIGRATION_STATE_OPTIONS } from "../constants";

export function CommunityTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: config, isLoading } = useQuery({
    queryKey: ["community-config"],
    queryFn: getCommunityConfig,
  });
  const [form, setForm] = useState(() => createCommunityForm());
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (config) {
      setForm(createCommunityForm(config));
      setFormError("");
    }
  }, [config]);

  const save = useMutation({
    mutationFn: () => {
      setFormError("");
      return updateCommunityConfig(communityFormToUpdate(form));
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["community-config"] });
      setForm(createCommunityForm(saved));
    },
    onError: (error) => {
      setFormError(error instanceof Error ? error.message : t("siteConfig.commentSaveError"));
    },
  });

  if (isLoading && !config) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  const updateField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Card className="mt-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">{t("siteConfig.community")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("siteConfig.communityDescription")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <Label>{t("siteConfig.commentProvider")}</Label>
            <Input value={form.provider} disabled />
          </div>
          <div className="space-y-1">
            <Label>{t("siteConfig.commentServerUrl")}</Label>
            <Input value={form.server_url} onChange={(e) => updateField("server_url", e.target.value)} placeholder="https://waline.example.com" />
          </div>
          <div className="space-y-1">
            <Label>{t("siteConfig.commentMigrationState")}</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.migration_state}
              onChange={(e) => updateField("migration_state", e.target.value)}
            >
              {MIGRATION_STATE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>{t("siteConfig.commentLoginMode")}</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.login_mode}
              onChange={(e) => updateField("login_mode", e.target.value)}
            >
              {LOGIN_MODE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <Label>{t("siteConfig.commentAvatarStrategy")}</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={form.avatar_strategy}
              onChange={(e) => updateField("avatar_strategy", e.target.value)}
            >
              {AVATAR_STRATEGY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.enable_enjoy_search}
              onChange={(e) => updateField("enable_enjoy_search", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            <span>{t("siteConfig.commentEnableEnjoySearch")}</span>
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

        <div className="space-y-1">
          <Label>{t("siteConfig.commentMeta")}</Label>
          <Input value={form.meta} onChange={(e) => updateField("meta", e.target.value)} placeholder="nick, mail" />
        </div>
        <div className="space-y-1">
          <Label>{t("siteConfig.commentRequiredMeta")}</Label>
          <Input value={form.required_meta} onChange={(e) => updateField("required_meta", e.target.value)} placeholder="nick" />
        </div>
        <div className="space-y-1">
          <Label>{t("siteConfig.commentEmojiPresets")}</Label>
          <Input value={form.emoji_presets} onChange={(e) => updateField("emoji_presets", e.target.value)} placeholder="apple, weibo, qq, bilibili, twemoji, github" />
        </div>
        <div className="space-y-1">
          <Label>{t("siteConfig.commentSurfaces")}</Label>
          <Textarea
            value={form.surfaces}
            onChange={(e) => updateField("surfaces", e.target.value)}
            rows={8}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">{t("siteConfig.commentSurfacesHint")}</p>
        </div>
        <div className="space-y-1">
          <Label>{t("siteConfig.commentOauthUrl")}</Label>
          <Input value={form.oauth_url} onChange={(e) => updateField("oauth_url", e.target.value)} placeholder="https://accounts.google.com/..." />
        </div>
        <div className="space-y-1">
          <Label>{t("siteConfig.commentHelperCopy")}</Label>
          <Textarea
            value={form.helper_copy}
            onChange={(e) => updateField("helper_copy", e.target.value)}
            rows={4}
            placeholder={t("siteConfig.commentHelperHint")}
          />
          <p className="text-xs text-muted-foreground">{t("siteConfig.commentHelperHint")}</p>
        </div>

        {formError && (
          <p className="text-sm text-destructive">{formError}</p>
        )}

        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          <Save className="h-4 w-4 mr-2" />
          {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}
