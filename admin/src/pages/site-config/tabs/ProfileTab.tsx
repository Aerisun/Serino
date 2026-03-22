import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getProfile, updateProfile } from "@/api/endpoints/site-config";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent } from "@/components/ui/Card";
import { Save } from "lucide-react";
import { useI18n } from "@/i18n";

export function ProfileTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({ queryKey: ["site-profile"], queryFn: getProfile });
  const [form, setForm] = useState({ name: "", title: "", bio: "", role: "", footer_text: "", hero_video_url: "" });

  useEffect(() => {
    if (profile) setForm({ name: profile.name, title: profile.title, bio: profile.bio, role: profile.role, footer_text: profile.footer_text, hero_video_url: profile.hero_video_url || "" });
  }, [profile]);

  const save = useMutation({
    mutationFn: () => updateProfile(form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["site-profile"] }),
  });

  if (isLoading) return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;

  const fieldLabels: Record<string, string> = {
    name: t("siteConfig.siteName"),
    title: t("siteConfig.siteTitle"),
    role: t("siteConfig.role"),
    footer_text: t("siteConfig.footerText"),
    hero_video_url: "首页视频 URL",
  };

  return (
    <Card className="mt-4 max-w-2xl">
      <CardContent className="pt-6 space-y-4">
        {(["name", "title", "role", "footer_text", "hero_video_url"] as const).map((key) => (
          <div key={key} className="space-y-2">
            <Label>{fieldLabels[key]}</Label>
            <Input value={form[key]} onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))} />
          </div>
        ))}
        <div className="space-y-2">
          <Label>{t("siteConfig.bio")}</Label>
          <Textarea value={form.bio} onChange={(e) => setForm((p) => ({ ...p, bio: e.target.value }))} rows={4} />
        </div>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          <Save className="h-4 w-4 mr-2" /> {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}
