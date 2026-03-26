import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
} from "@serino/api-client/admin";
import type { SiteProfileAdminRead } from "@serino/api-client/models";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { useI18n } from "@/i18n";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

export function MoreTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const profile = raw?.data as SiteProfileAdminRead | undefined;
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (profile) {
      setFeatureFlags(profile.feature_flags ?? {});
    }
  }, [profile]);

  const save = useUpdateProfileApiV1AdminSiteConfigProfilePut({
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

  if (isLoading) {
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
    {
      key: "social_sharing",
      label: t("siteConfig.featureSocialSharing"),
      desc: t("siteConfig.featureSocialSharingDesc"),
    },
  ] as const;

  return (
    <Card className="mt-4 max-w-2xl">
      <CardContent className="pt-6 space-y-4">
        <div>
          <h3 className="text-lg font-semibold">{t("siteConfig.featureFlags")}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("siteConfig.featureFlagsDescription")}
          </p>
        </div>

        <div className="space-y-4">
          {flags.map((flag) => {
            const enabled = featureFlags[flag.key] ?? true;
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
                  onClick={() =>
                    setFeatureFlags((prev) => ({
                      ...prev,
                      [flag.key]: !enabled,
                    }))
                  }
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

        <Button
          onClick={() =>
            save.mutate({
              data: {
                name: profile?.name ?? "",
                title: profile?.title ?? "",
                bio: profile?.bio ?? "",
                role: profile?.role ?? "",
                footer_text: profile?.footer_text ?? "",
                hero_video_url: profile?.hero_video_url ?? "",
                feature_flags: featureFlags,
              },
            })
          }
          disabled={save.isPending}
        >
          <Save className="mr-2 h-4 w-4" />
          {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}