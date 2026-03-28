import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  getGetRuntimeSettingsApiV1AdminSiteConfigRuntimeGetQueryKey,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useGetRuntimeSettingsApiV1AdminSiteConfigRuntimeGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
  useUpdateRuntimeSettingsApiV1AdminSiteConfigRuntimePut,
} from "@serino/api-client/admin";
import type {
  RuntimeSiteSettingsAdminRead,
  SiteProfileAdminRead,
} from "@serino/api-client/models";
import { toast } from "sonner";
import { useI18n } from "@/i18n";
import { Card, CardContent } from "@/components/ui/Card";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { Button } from "@/components/ui/Button";
import { HintBanner } from "@/components/ui/HintBanner";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";

interface RuntimeStaticPageFormItem {
  path: string;
  changefreq: string;
  priority: string;
}

interface RuntimeSettingsFormState {
  public_site_url: string;
  production_cors_origins: string;
  seo_default_title: string;
  seo_default_description: string;
  rss_title: string;
  rss_description: string;
  robots_indexing_enabled: boolean;
  sitemap_static_pages: RuntimeStaticPageFormItem[];
}

const CHANGEFREQ_OPTIONS = ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"] as const;

function cloneStaticPages(pages?: RuntimeSiteSettingsAdminRead["sitemap_static_pages"] | null): RuntimeStaticPageFormItem[] {
  const items = (pages ?? []).map((item) => ({
    path: item.path ?? "",
    changefreq: item.changefreq ?? "weekly",
    priority: item.priority ?? "0.5",
  }));
  return items.length ? items : [{ path: "/", changefreq: "daily", priority: "1.0" }];
}

function createRuntimeForm(runtime?: RuntimeSiteSettingsAdminRead | null): RuntimeSettingsFormState {
  return {
    public_site_url: runtime?.public_site_url ?? "",
    production_cors_origins: (runtime?.production_cors_origins ?? []).join("\n"),
    seo_default_title: runtime?.seo_default_title ?? "",
    seo_default_description: runtime?.seo_default_description ?? "",
    rss_title: runtime?.rss_title ?? "",
    rss_description: runtime?.rss_description ?? "",
    robots_indexing_enabled: runtime?.robots_indexing_enabled ?? true,
    sitemap_static_pages: cloneStaticPages(runtime?.sitemap_static_pages),
  };
}

function trimTrailingSlash(value: string): string {
  const trimmed = value.trim();
  return trimmed.replace(/\/+$/, "");
}

function buildRuntimePayload(form: RuntimeSettingsFormState, t: (key: string) => string) {
  const publicSiteUrl = trimTrailingSlash(form.public_site_url);
  if (publicSiteUrl) {
    try {
      new URL(publicSiteUrl);
    } catch {
      return { payload: null, error: t("siteConfig.runtimeSettingsInvalidUrl") };
    }
  }

  const staticPages: RuntimeStaticPageFormItem[] = [];
  for (const item of form.sitemap_static_pages) {
    const path = item.path.trim();
    const priority = item.priority.trim() || "0.5";
    const changefreq = item.changefreq.trim() || "weekly";

    if (!path) {
      continue;
    }
    if (!path.startsWith("/")) {
      return { payload: null, error: t("siteConfig.runtimeSettingsInvalidPath") };
    }
    const numericPriority = Number(priority);
    if (Number.isNaN(numericPriority) || numericPriority < 0 || numericPriority > 1) {
      return { payload: null, error: t("siteConfig.runtimeSettingsInvalidPriority") };
    }
    staticPages.push({
      path,
      changefreq,
      priority: numericPriority.toFixed(1),
    });
  }

  return {
    payload: {
      public_site_url: publicSiteUrl,
      production_cors_origins: form.production_cors_origins
        .split("\n")
        .map((item) => trimTrailingSlash(item))
        .filter(Boolean),
      seo_default_title: form.seo_default_title.trim(),
      seo_default_description: form.seo_default_description.trim(),
      rss_title: form.rss_title.trim(),
      rss_description: form.rss_description.trim(),
      robots_indexing_enabled: form.robots_indexing_enabled,
      sitemap_static_pages: staticPages,
    },
    error: "",
  };
}

export function MoreTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profileRaw, isLoading: profileLoading } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const { data: runtimeRaw, isLoading: runtimeLoading } = useGetRuntimeSettingsApiV1AdminSiteConfigRuntimeGet();
  const profile = profileRaw?.data as SiteProfileAdminRead | undefined;
  const runtime = runtimeRaw?.data as RuntimeSiteSettingsAdminRead | undefined;

  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});
  const [runtimeForm, setRuntimeForm] = useState<RuntimeSettingsFormState>(() => createRuntimeForm());
  const [savedRuntimeForm, setSavedRuntimeForm] = useState<RuntimeSettingsFormState>(() => createRuntimeForm());
  const [runtimeError, setRuntimeError] = useState("");

  useEffect(() => {
    if (profile) {
      setFeatureFlags(profile.feature_flags ?? {});
    }
  }, [profile]);

  useEffect(() => {
    if (runtime) {
      const nextForm = createRuntimeForm(runtime);
      setRuntimeForm(nextForm);
      setSavedRuntimeForm(nextForm);
      setRuntimeError("");
    }
  }, [runtime]);

  const saveFeatureFlags = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const saveRuntime = useUpdateRuntimeSettingsApiV1AdminSiteConfigRuntimePut({
    mutation: {
      onSuccess: (response) => {
        queryClient.invalidateQueries({ queryKey: getGetRuntimeSettingsApiV1AdminSiteConfigRuntimeGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        if (response.data) {
          const nextForm = createRuntimeForm(response.data as RuntimeSiteSettingsAdminRead);
          setRuntimeForm(nextForm);
          setSavedRuntimeForm(nextForm);
          setRuntimeError("");
        }
      },
      onError: (error: any) => {
        setRuntimeError(error?.response?.data?.detail || t("common.operationFailed"));
      },
    },
  });

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
    {
      key: "social_sharing",
      label: t("siteConfig.featureSocialSharing"),
      desc: t("siteConfig.featureSocialSharingDesc"),
    },
  ] as const;

  const resolvedFeatureFlags = flags.reduce<Record<string, boolean>>((acc, flag) => {
    acc[flag.key] = featureFlags[flag.key] ?? true;
    return acc;
  }, {});

  const buildFeatureFlagSaveData = (nextFeatureFlags: Record<string, boolean>) => ({
    name: profile?.name ?? "",
    title: profile?.title ?? "",
    bio: profile?.bio ?? "",
    role: profile?.role ?? "",
    footer_text: profile?.footer_text ?? "",
    hero_video_url: profile?.hero_video_url ?? "",
    feature_flags: nextFeatureFlags,
  });

  const handleToggle = async (flagKey: string) => {
    const previousFlags = resolvedFeatureFlags;
    const nextFeatureFlags = {
      ...resolvedFeatureFlags,
      [flagKey]: !resolvedFeatureFlags[flagKey],
    };

    setFeatureFlags(nextFeatureFlags);

    try {
      await saveFeatureFlags.mutateAsync({ data: buildFeatureFlagSaveData(nextFeatureFlags) });
    } catch {
      setFeatureFlags(previousFlags);
    }
  };

  const runtimeBuild = useMemo(() => buildRuntimePayload(runtimeForm, t), [runtimeForm, t]);
  const savedRuntimeBuild = useMemo(() => buildRuntimePayload(savedRuntimeForm, t), [savedRuntimeForm, t]);
  const runtimeDirty = JSON.stringify(runtimeBuild.payload) !== JSON.stringify(savedRuntimeBuild.payload);
  const canonicalPreviewBase = runtimeBuild.payload?.public_site_url || trimTrailingSlash(runtime?.public_site_url ?? "");

  const updateRuntimeField = <K extends keyof RuntimeSettingsFormState>(key: K, value: RuntimeSettingsFormState[K]) => {
    setRuntimeForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateStaticPage = <K extends keyof RuntimeStaticPageFormItem>(index: number, key: K, value: RuntimeStaticPageFormItem[K]) => {
    setRuntimeForm((prev) => ({
      ...prev,
      sitemap_static_pages: prev.sitemap_static_pages.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      ),
    }));
  };

  const addStaticPage = () => {
    setRuntimeForm((prev) => ({
      ...prev,
      sitemap_static_pages: [...prev.sitemap_static_pages, { path: "", changefreq: "weekly", priority: "0.5" }],
    }));
  };

  const removeStaticPage = (index: number) => {
    setRuntimeForm((prev) => ({
      ...prev,
      sitemap_static_pages:
        prev.sitemap_static_pages.length === 1
          ? [{ path: "", changefreq: "weekly", priority: "0.5" }]
          : prev.sitemap_static_pages.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const handleSaveRuntime = async () => {
    if (!runtimeBuild.payload) {
      setRuntimeError(runtimeBuild.error || t("common.operationFailed"));
      return;
    }
    setRuntimeError("");
    await saveRuntime.mutateAsync({ data: runtimeBuild.payload });
  };

  if (profileLoading || runtimeLoading) {
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;
  }

  return (
    <div className="mt-4 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
      <Card className="max-w-2xl">
        <CardContent className="space-y-4 pt-6">
          <div>
            <h3 className="text-lg font-semibold">{t("siteConfig.featureFlags")}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("siteConfig.featureFlagsDescription")}
            </p>
          </div>

          <div className="space-y-4">
            {flags.map((flag) => {
              const enabled = resolvedFeatureFlags[flag.key];
              return (
                <label
                  key={flag.key}
                  className="flex items-center justify-between gap-4 rounded-xl border border-border/60 bg-background/60 px-4 py-3 shadow-sm backdrop-blur-sm transition-colors hover:bg-background/75"
                >
                  <div className="space-y-1">
                    <div className="text-sm font-medium">{flag.label}</div>
                    <div className="text-xs text-muted-foreground">{flag.desc}</div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={enabled}
                    onClick={() => void handleToggle(flag.key)}
                    disabled={saveFeatureFlags.isPending}
                    className={cn(
                      "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-all",
                      enabled
                        ? "border-emerald-400/40 bg-emerald-500/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_0_0_1px_rgba(16,185,129,0.12)]"
                        : "border-slate-400/30 bg-slate-500/15 shadow-[inset_0_1px_0_rgba(255,255,255,0.15),0_0_0_1px_rgba(148,163,184,0.08)]",
                    )}
                  >
                    <span
                      className={cn(
                        "pointer-events-none block h-5 w-5 rounded-full bg-background shadow-md ring-1 ring-black/5 transition-transform",
                        enabled ? "translate-x-6" : "translate-x-1",
                      )}
                    />
                  </button>
                </label>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-6 pt-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">{t("siteConfig.runtimeSettings")}</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {t("siteConfig.runtimeSettingsDescription")}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {runtimeDirty ? <PendingSaveBadge /> : null}
              <DirtySaveButton dirty={runtimeDirty} saving={saveRuntime.isPending} onClick={() => void handleSaveRuntime()} />
            </div>
          </div>

          <HintBanner>
            <div className="space-y-1">
              <p>{t("siteConfig.runtimeSettingsHint")}</p>
              <p className="text-xs text-muted-foreground">{t("siteConfig.runtimeSettingsHintSecondary")}</p>
            </div>
          </HintBanner>

          <HintBanner>{t("siteConfig.runtimeSectionsHint")}</HintBanner>

          <div className="space-y-3">
            <CollapsibleSection
              title={t("siteConfig.runtimeSectionGeneral")}
              badge={t("siteConfig.runtimeSectionGeneralBadge")}
              defaultOpen
            >
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2 lg:col-span-2">
                  <LabelWithHelp
                    label={t("siteConfig.runtimePublicSiteUrl")}
                    description={t("siteConfig.runtimePublicSiteUrlHelp")}
                    usageTitle={t("siteConfig.runtimeExamples")}
                    usageItems={["https://example.com", "https://blog.example.com"]}
                  />
                  <Input
                    value={runtimeForm.public_site_url}
                    onChange={(e) => updateRuntimeField("public_site_url", e.target.value)}
                    placeholder="https://example.com"
                  />
                </div>

                <div className="space-y-2 lg:col-span-2">
                  <LabelWithHelp
                    label={t("siteConfig.runtimeProductionCorsOrigins")}
                    description={t("siteConfig.runtimeProductionCorsOriginsHelp")}
                    usageTitle={t("siteConfig.runtimeExamples")}
                    usageItems={["https://example.com", "https://admin.example.com"]}
                  />
                  <Textarea
                    value={runtimeForm.production_cors_origins}
                    onChange={(e) => updateRuntimeField("production_cors_origins", e.target.value)}
                    rows={4}
                    placeholder={t("siteConfig.runtimeProductionCorsOriginsPlaceholder")}
                  />
                </div>
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              title={t("siteConfig.runtimeSectionPreview")}
              badge={t("siteConfig.runtimeSectionPreviewBadge")}
              defaultOpen
            >
              <div className="grid gap-3 md:grid-cols-3">
                {[
                  { label: t("siteConfig.runtimePreviewSitemap"), suffix: "/sitemap.xml" },
                  { label: t("siteConfig.runtimePreviewRobots"), suffix: "/robots.txt" },
                  { label: t("siteConfig.runtimePreviewFeed"), suffix: "/feeds/posts.xml" },
                ].map((item) => (
                  <div key={item.suffix} className="rounded-2xl border border-border/60 bg-background/55 px-4 py-3">
                    <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                      {item.label}
                    </div>
                    <div className="mt-2 break-all text-sm text-foreground/88">
                      {canonicalPreviewBase ? `${canonicalPreviewBase}${item.suffix}` : t("siteConfig.runtimePreviewPending")}
                    </div>
                  </div>
                ))}
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              title={t("siteConfig.runtimeSectionSeo")}
              badge={t("siteConfig.runtimeSectionSeoBadge")}
              defaultOpen
            >
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <LabelWithHelp
                    label={t("siteConfig.runtimeSeoDefaultTitle")}
                    description={t("siteConfig.runtimeSeoDefaultTitleHelp")}
                  />
                  <Input
                    value={runtimeForm.seo_default_title}
                    onChange={(e) => updateRuntimeField("seo_default_title", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <LabelWithHelp
                    label={t("siteConfig.runtimeRssTitle")}
                    description={t("siteConfig.runtimeRssTitleHelp")}
                  />
                  <Input
                    value={runtimeForm.rss_title}
                    onChange={(e) => updateRuntimeField("rss_title", e.target.value)}
                  />
                </div>
                <div className="space-y-2 lg:col-span-2">
                  <LabelWithHelp
                    label={t("siteConfig.runtimeSeoDefaultDescription")}
                    description={t("siteConfig.runtimeSeoDefaultDescriptionHelp")}
                  />
                  <Textarea
                    value={runtimeForm.seo_default_description}
                    onChange={(e) => updateRuntimeField("seo_default_description", e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="space-y-2 lg:col-span-2">
                  <LabelWithHelp
                    label={t("siteConfig.runtimeRssDescription")}
                    description={t("siteConfig.runtimeRssDescriptionHelp")}
                  />
                  <Textarea
                    value={runtimeForm.rss_description}
                    onChange={(e) => updateRuntimeField("rss_description", e.target.value)}
                    rows={3}
                  />
                </div>
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              title={t("siteConfig.runtimeSectionIndexing")}
              badge={t("siteConfig.runtimeSectionIndexingBadge")}
              defaultOpen
            >
              <AppleSwitch
                checked={runtimeForm.robots_indexing_enabled}
                onCheckedChange={(checked) => updateRuntimeField("robots_indexing_enabled", checked)}
                label={t("siteConfig.runtimeRobotsIndexingEnabled")}
                description={t("siteConfig.runtimeRobotsIndexingEnabledHelp")}
              />
            </CollapsibleSection>

            <CollapsibleSection
              title={t("siteConfig.runtimeSectionSitemap")}
              badge={t("siteConfig.runtimeSectionSitemapBadge")}
              defaultOpen
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <LabelWithHelp
                      label={t("siteConfig.runtimeSitemapStaticPages")}
                      description={t("siteConfig.runtimeSitemapStaticPagesHelp")}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t("siteConfig.runtimeSitemapStaticPagesSecondary")}
                    </p>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={addStaticPage}>
                    <Plus className="mr-2 h-4 w-4" />
                    {t("siteConfig.runtimeAddStaticPage")}
                  </Button>
                </div>

                <div className="space-y-3">
                  {runtimeForm.sitemap_static_pages.map((item, index) => (
                    <div key={`${index}-${item.path}-${item.changefreq}`} className="rounded-2xl border border-border/60 bg-background/55 p-4">
                      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,0.9fr)_minmax(0,0.7fr)_auto]">
                        <div className="space-y-2">
                          <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                            {t("siteConfig.runtimePath")}
                          </div>
                          <Input
                            value={item.path}
                            onChange={(e) => updateStaticPage(index, "path", e.target.value)}
                            placeholder="/posts"
                          />
                        </div>
                        <div className="space-y-2">
                          <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                            {t("siteConfig.runtimeChangefreq")}
                          </div>
                          <Select value={item.changefreq} onValueChange={(value) => updateStaticPage(index, "changefreq", value)}>
                            <SelectTrigger>
                              <SelectValue placeholder={t("siteConfig.runtimeChangefreq")} />
                            </SelectTrigger>
                            <SelectContent>
                              {CHANGEFREQ_OPTIONS.map((option) => (
                                <SelectItem key={option} value={option}>
                                  {option}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                            {t("siteConfig.runtimePriority")}
                          </div>
                          <Input
                            value={item.priority}
                            onChange={(e) => updateStaticPage(index, "priority", e.target.value)}
                            placeholder="0.5"
                          />
                        </div>
                        <div className="flex items-end">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeStaticPage(index)}
                            aria-label={t("siteConfig.runtimeRemoveStaticPage")}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CollapsibleSection>
          </div>

          {runtimeError ? (
            <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
              {runtimeError}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
