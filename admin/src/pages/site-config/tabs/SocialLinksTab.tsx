import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getProfile,
  listSocialLinks, createSocialLink, updateSocialLink, deleteSocialLink,
} from "@/api/endpoints/site-config";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { DataTable } from "@/components/DataTable";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useI18n } from "@/i18n";
import type { SocialLink } from "@/types/models";

export function SocialLinksTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profile } = useQuery({ queryKey: ["site-profile"], queryFn: getProfile });
  const { data } = useQuery({ queryKey: ["social-links"], queryFn: () => listSocialLinks() });
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", href: "", icon_key: "", placement: "hero", order_index: 0 });

  const profileId = profile?.id ?? "";

  const create = useMutation({
    mutationFn: () => createSocialLink({ ...form, site_profile_id: profileId }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["social-links"] }); setOpen(false); resetForm(); },
  });

  const update = useMutation({
    mutationFn: () => updateSocialLink(editingId!, form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["social-links"] }); setEditingId(null); setOpen(false); resetForm(); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteSocialLink(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["social-links"] }),
  });

  function resetForm() {
    setForm({ name: "", href: "", icon_key: "", placement: "hero", order_index: 0 });
  }

  function startEdit(link: SocialLink) {
    setEditingId(link.id);
    setForm({ name: link.name, href: link.href, icon_key: link.icon_key, placement: link.placement, order_index: link.order_index });
    setOpen(true);
  }

  const fieldLabels: Record<string, string> = {
    name: t("siteConfig.name"),
    href: t("siteConfig.href"),
    icon_key: t("siteConfig.iconKey"),
    placement: t("siteConfig.placement"),
  };

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); resetForm(); } }}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addLink")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingId ? t("siteConfig.editSocialLink") : t("siteConfig.newSocialLink")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              {(["name", "href", "icon_key", "placement"] as const).map((k) => (
                <div key={k} className="space-y-1">
                  <Label>{fieldLabels[k]}</Label>
                  <Input value={(form as any)[k]} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))} />
                </div>
              ))}
              <div className="space-y-1">
                <Label>{t("common.order")}</Label>
                <Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} />
              </div>
              <Button onClick={() => editingId ? update.mutate() : create.mutate()} disabled={create.isPending || update.isPending}>
                {editingId ? t("common.save") : t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        <DataTable<SocialLink>
          columns={[
            { header: t("siteConfig.name"), accessor: "name" },
            { header: t("siteConfig.url"), accessor: "href" },
            { header: t("siteConfig.icon"), accessor: "icon_key" },
            { header: t("siteConfig.placement"), accessor: "placement" },
            { header: t("common.order"), accessor: "order_index" as any },
            { header: "", accessor: (row) => (
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); startEdit(row); }}><Pencil className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); del.mutate(row.id); }}><Trash2 className="h-4 w-4" /></Button>
              </div>
            )},
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
        />
      </div>
    </div>
  );
}
