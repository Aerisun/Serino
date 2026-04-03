import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useListSocialLinks,
  useCreateSocialLinks,
  useUpdateSocialLinks,
  useDeleteSocialLinks,
  getListSocialLinksQueryKey,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { DataTable } from "@/components/DataTable";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import type { SocialLinkAdminRead } from "@serino/api-client/models";
import { optionLabel, SOCIAL_SOFTWARE_LABELS, SOCIAL_SOFTWARE_OPTIONS } from "../constants";

export function SocialLinksTab() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const { data: profileRaw } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const { data: raw } = useListSocialLinks();
  const data = raw?.data;
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", href: "", icon_key: "", placement: "hero", order_index: 0 });

  const profileId = profileRaw?.data?.id ?? "";

  const create = useCreateSocialLinks({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListSocialLinksQueryKey() }); setOpen(false); resetForm(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { toast.error(extractApiErrorMessage(error, t("common.operationFailed"))); },
    },
  });

  const update = useUpdateSocialLinks({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListSocialLinksQueryKey() }); setEditingId(null); setOpen(false); resetForm(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { toast.error(extractApiErrorMessage(error, t("common.operationFailed"))); },
    },
  });

  const del = useDeleteSocialLinks({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListSocialLinksQueryKey() }); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { toast.error(extractApiErrorMessage(error, t("common.operationFailed"))); },
    },
  });

  function resetForm() {
    setForm({ name: "", href: "", icon_key: "", placement: "hero", order_index: 0 });
  }

  function startEdit(link: SocialLinkAdminRead) {
    setEditingId(link.id);
    setForm({ name: link.name, href: link.href, icon_key: link.icon_key, placement: link.placement, order_index: link.order_index });
    setOpen(true);
  }

  const updateSoftware = (iconKey: string) => {
    setForm((prev) => ({
      ...prev,
      icon_key: iconKey,
      name: optionLabel(SOCIAL_SOFTWARE_LABELS, iconKey, lang),
    }));
  };

  const fieldLabels: Record<string, string> = {
    name: t("siteConfig.name"),
    href: t("siteConfig.href"),
  };

  const placementOptions = [
    { value: "hero", label: t("siteConfig.heroPlacement") },
    { value: "footer", label: t("siteConfig.footerPlacement") },
    { value: "both", label: t("siteConfig.bothPlacement") },
  ] as const;

  const placementLabel = (value: string) =>
    placementOptions.find((option) => option.value === value)?.label ?? value;

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); resetForm(); } }}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addLink")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingId ? t("siteConfig.editSocialLink") : t("siteConfig.newSocialLink")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>{fieldLabels.name}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.icon_key}
                  onChange={(e) => updateSoftware(e.target.value)}
                >
                  <option value="">{t("siteConfig.selectSoftware")}</option>
                  {SOCIAL_SOFTWARE_OPTIONS.map((v) => (
                    <option key={v} value={v}>
                      {optionLabel(SOCIAL_SOFTWARE_LABELS, v, lang)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label>{fieldLabels.href}</Label>
                <Input value={form.href} onChange={(e) => setForm((p) => ({ ...p, href: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label>{t("common.order")}</Label>
                <Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} />
              </div>
              <div className="space-y-1">
                <Label>{t("siteConfig.placement")}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.placement}
                  onChange={(e) => setForm((p) => ({ ...p, placement: e.target.value }))}
                >
                  {placementOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <Button onClick={() => editingId ? update.mutate({ itemId: editingId, data: { ...form, placement: form.placement || "hero" } }) : create.mutate({ data: { ...form, site_profile_id: profileId, placement: form.placement || "hero" } })} disabled={create.isPending || update.isPending || !form.icon_key || !form.href}>
                {editingId ? t("common.save") : t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        <DataTable<SocialLinkAdminRead>
          columns={[
            { header: t("siteConfig.software"), accessor: "name" },
            { header: t("siteConfig.url"), accessor: "href" },
            { header: t("siteConfig.placement"), accessor: (row) => placementLabel(row.placement) },
            { header: t("common.order"), accessor: "order_index" as any },
            { header: "", accessor: (row) => (
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); startEdit(row); }}><Pencil className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); del.mutate({ itemId: row.id }); }}><Trash2 className="h-4 w-4" /></Button>
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
