import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent } from "@/components/ui/Card";
import { Save } from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { SiteProfileAdminRead } from "@serino/api-client/models";

export function ProfileTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const profile = raw?.data as SiteProfileAdminRead | undefined;
  const [form, setForm] = useState({
    name: "",
    title: "",
    bio: "",
    role: "",
    footer_text: "",
    hero_video_url: "",
  });
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (profile) {
      setForm({
        name: profile.name,
        title: profile.title,
        bio: profile.bio,
        role: profile.role,
        footer_text: profile.footer_text,
        hero_video_url: profile.hero_video_url || "",
      });
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

  if (isLoading)
    return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;

  const fieldLabels: Record<string, string> = {
    name: t("siteConfig.siteName"),
    title: t("siteConfig.siteTitle"),
    role: t("siteConfig.role"),
    footer_text: t("siteConfig.footerText"),
    hero_video_url: t("siteConfig.heroVideoUrl"),
  };

  return (
    <>
      <Card className="mt-4 max-w-2xl">
        <CardContent className="pt-6 space-y-4">
          {(
            ["name", "title", "role", "footer_text", "hero_video_url"] as const
          ).map((key) => (
            <div key={key} className="space-y-2">
              <Label>{fieldLabels[key]}</Label>
              <Input
                value={form[key]}
                onChange={(e) =>
                  setForm((p) => ({ ...p, [key]: e.target.value }))
                }
              />
            </div>
          ))}
          <div className="space-y-2">
            <Label>{t("siteConfig.bio")}</Label>
            <Textarea
              value={form.bio}
              onChange={(e) => setForm((p) => ({ ...p, bio: e.target.value }))}
              rows={4}
            />
          </div>
          <Button onClick={() => save.mutate({ data: { ...form, feature_flags: featureFlags } })} disabled={save.isPending}>
            <Save className="h-4 w-4 mr-2" />{" "}
            {save.isPending ? t("common.saving") : t("common.save")}
          </Button>
        </CardContent>
      </Card>

      {/* Feature Flags */}
      <div className="rounded-lg border bg-card p-6 mt-6 max-w-2xl">
        <h3 className="text-lg font-semibold mb-1">
          {t("siteConfig.featureFlags")}
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          {t("siteConfig.featureFlagsDescription")}
        </p>
        <div className="space-y-4">
          {[
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
          ].map((flag) => (
            <label
              key={flag.key}
              className="flex items-center justify-between gap-4 py-2"
            >
              <div>
                <div className="text-sm font-medium">{flag.label}</div>
                <div className="text-xs text-muted-foreground">{flag.desc}</div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={featureFlags[flag.key] ?? true}
                onClick={() =>
                  setFeatureFlags((prev) => ({
                    ...prev,
                    [flag.key]: !(prev[flag.key] ?? true),
                  }))
                }
                className={cn(
                  "relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors",
                  (featureFlags[flag.key] ?? true) ? "bg-primary" : "bg-muted",
                )}
              >
                <span
                  className={cn(
                    "pointer-events-none block h-4 w-4 rounded-full bg-background shadow-sm transition-transform",
                    (featureFlags[flag.key] ?? true)
                      ? "translate-x-4"
                      : "translate-x-0",
                  )}
                />
              </button>
            </label>
          ))}
        </div>
      </div>
    </>
  );
}
