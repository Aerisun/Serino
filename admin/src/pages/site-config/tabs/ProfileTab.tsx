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
import { ResourceUploadField } from "@/components/ResourceUploadField";
import { Save } from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { SiteProfileAdminRead } from "@serino/api-client/models";

export function ProfileTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw, isLoading } =
    useGetProfileApiV1AdminSiteConfigProfileGet();
  const profile = raw?.data as SiteProfileAdminRead | undefined;
  const [form, setForm] = useState({
    name: "",
    title: "",
    bio: "",
    role: "",
    footer_text: "",
    og_image: "",
    hero_image_url: "",
    hero_poster_url: "",
    hero_video_url: "",
  });

  useEffect(() => {
    if (profile) {
      setForm({
        name: profile.name,
        title: profile.title,
        bio: profile.bio,
        role: profile.role,
        footer_text: profile.footer_text,
        og_image: profile.og_image,
        hero_image_url: profile.hero_image_url || "",
        hero_poster_url: profile.hero_poster_url || "",
        hero_video_url: profile.hero_video_url || "",
      });
    }
  }, [profile]);

  const save = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
        });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg =
          error?.response?.data?.detail || t("common.operationFailed");
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
  };

  return (
    <>
      <Card className="mt-4 max-w-2xl">
        <CardContent className="pt-6 space-y-4">
          {(["name", "title", "role", "footer_text"] as const).map((key) => (
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
          <ResourceUploadField
            label="Hero 视觉图"
            value={form.hero_image_url}
            category="hero-image"
            accept="image/*"
            placeholder="上传或填写 Hero 视觉图地址"
            note="首页 Hero 默认视觉图"
            uniqueByCategory
            onChange={(value) =>
              setForm((p) => ({ ...p, hero_image_url: value }))
            }
          />
          <ResourceUploadField
            label="Hero 视频封面图"
            value={form.hero_poster_url}
            category="hero-poster"
            accept="image/*"
            placeholder="上传或填写 Hero 视频封面图地址"
            note="首页 Hero 视频默认封面图"
            uniqueByCategory
            onChange={(value) =>
              setForm((p) => ({ ...p, hero_poster_url: value }))
            }
          />
          <ResourceUploadField
            label={t("siteConfig.heroVideoUrl")}
            value={form.hero_video_url}
            category="hero-media"
            accept="image/*,video/*"
            placeholder="上传或填写 Hero 视频/封面地址"
            note="首页 Hero 视频资源"
            uniqueByCategory
            onChange={(value) =>
              setForm((p) => ({ ...p, hero_video_url: value }))
            }
          />
          <ResourceUploadField
            label="OG 图地址（视频失效的时候显示作首页背景）"
            value={form.og_image}
            category="og-image"
            accept="image/*"
            placeholder="上传或填写 OG 图地址"
            note="站点默认 OG 分享图"
            uniqueByCategory
            onChange={(value) => setForm((p) => ({ ...p, og_image: value }))}
          />
          <div className="space-y-2">
            <Label>{t("siteConfig.bio")}</Label>
            <Textarea
              value={form.bio}
              onChange={(e) => setForm((p) => ({ ...p, bio: e.target.value }))}
              rows={4}
            />
          </div>
          <Button
            onClick={() => save.mutate({ data: form })}
            disabled={save.isPending}
          >
            <Save className="h-4 w-4 mr-2" />{" "}
            {save.isPending ? t("common.saving") : t("common.save")}
          </Button>
        </CardContent>
      </Card>
    </>
  );
}
