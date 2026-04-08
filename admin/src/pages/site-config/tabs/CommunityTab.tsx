import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { CommunityConfigAdminRead } from "@serino/api-client/models";
import {
  useGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGet,
  useUpdateCommunityConfigApiV1AdminSiteConfigCommunityConfigPut,
  getGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGetQueryKey,
} from "@serino/api-client/admin";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
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
import { toast } from "sonner";
import {
  createCommunityForm,
  communityFormToUpdate,
} from "@/lib/community-config";
import { useI18n } from "@/i18n";
import {
  MODERATION_MODE_LABELS,
  DEFAULT_SORTING_LABELS,
  optionLabel,
} from "../constants";

const MODERATION_MODE_OPTIONS = ["all_pending", "no_review"] as const;
const DEFAULT_SORTING_OPTIONS = ["latest", "oldest", "hottest"] as const;

export function CommunityTab() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const { data: resp, isLoading } =
    useGetCommunityConfigApiV1AdminSiteConfigCommunityConfigGet();
  const config = resp?.data;
  const [form, setForm] = useState(() => createCommunityForm());
  const [savedForm, setSavedForm] = useState(() => createCommunityForm());
  const [formError, setFormError] = useState("");
  const saveTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (config) {
      const nextForm = createCommunityForm(config);
      setForm(nextForm);
      setSavedForm(nextForm);
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
          const nextForm = createCommunityForm(saved.data as CommunityConfigAdminRead);
          setForm(nextForm);
          setSavedForm(nextForm);
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

  const effectiveSavedForm = savedForm ?? createCommunityForm(config);
  const currentPayload = communityFormToUpdate(form);
  const savedPayload = communityFormToUpdate(effectiveSavedForm);
  const hasChanges = JSON.stringify(currentPayload) !== JSON.stringify(savedPayload);

  useEffect(() => {
    if (!config || !hasChanges || save.isPending) {
      return undefined;
    }

    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = window.setTimeout(() => {
      save.mutate({ data: currentPayload });
    }, 450);

    return () => {
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [config, hasChanges, save.isPending, currentPayload, save]);

  if (isLoading && !config) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  const updateField = <K extends keyof typeof form>(
    key: K,
    value: (typeof form)[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const renderInlineSwitchLabel = (label: string, description: string) => (
    <span className="inline-flex items-center gap-1.5">
      <span>{label}</span>
      <LabelWithHelp
        hideLabel
        label={label}
        title={label}
        description={description}
      />
    </span>
  );

  return (
    <Card className="mt-4">
      <CardContent className="space-y-6 pt-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-1.5">
              <h3 className="text-lg font-semibold">{t("siteConfig.community")}</h3>
              <LabelWithHelp
                hideLabel
                label={t("siteConfig.community")}
                title={t("siteConfig.community")}
                description={t("siteConfig.sectionDescriptions.community")}
                usageTitle="提示"
                usageItems={[t("siteConfig.commentAutoSaveHint")]}
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
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
            checked={form.email_login_enabled}
            onCheckedChange={(checked) =>
              updateField("email_login_enabled", checked)
            }
            label={renderInlineSwitchLabel(
              t("siteConfig.commentAnonymousEnabled"),
              t("siteConfig.commentAnonymousEnabledDesc"),
            )}
          />
          <AppleSwitch
            checked={form.image_uploader}
            onCheckedChange={(checked) =>
              updateField("image_uploader", checked)
            }
            label={renderInlineSwitchLabel(
              t("siteConfig.commentImageUploader"),
              t("siteConfig.commentImageUploaderDesc"),
            )}
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
            </div>

            <div className="space-y-1">
              <Label>{t("siteConfig.commentEmojiPresets")}</Label>
              <Input
                value={form.emoji_presets}
                onChange={(e) => updateField("emoji_presets", e.target.value)}
                placeholder="weibo, qq, tieba, bilibili, twemoji, alus, bmoji"
              />
            </div>

            <div className="space-y-1">
              <LabelWithHelp
                label={t("siteConfig.commentSurfaces")}
                title={t("siteConfig.commentSurfaces")}
                description={t("siteConfig.commentSurfacesHint")}
              />
              <Textarea
                value={form.surfaces}
                onChange={(e) => updateField("surfaces", e.target.value)}
                rows={8}
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-1">
              <LabelWithHelp
                label={`${t("siteConfig.commentHelperCopy")} (${t("common.optional")})`}
                title={t("siteConfig.commentHelperCopy")}
                description={t("siteConfig.commentHelperHint")}
              />
              <Textarea
                value={form.helper_copy}
                onChange={(e) => updateField("helper_copy", e.target.value)}
                rows={4}
                placeholder={t("siteConfig.commentHelperHint")}
              />
            </div>
          </div>
        </CollapsibleSection>

        {formError && <p className="text-sm text-destructive">{formError}</p>}
      </CardContent>
    </Card>
  );
}
