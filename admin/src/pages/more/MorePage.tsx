import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
} from "@serino/api-client/admin";
import type { SiteProfileAdminRead } from "@serino/api-client/models";

import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/Card";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

export default function MorePage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const { data: profileRaw, isLoading } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const profile = profileRaw?.data as SiteProfileAdminRead | undefined;

  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (profile) {
      setFeatureFlags(profile.feature_flags ?? {});
    }
  }, [profile]);

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

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.more")}
        description={t("siteConfig.featureFlagsDescription")}
      />

      {isLoading ? (
        <p className="py-4 text-muted-foreground">{t("common.loading")}</p>
      ) : (
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
      )}
    </div>
  );
}
