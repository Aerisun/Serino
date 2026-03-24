import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useListPoems,
  useCreatePoems,
  useUpdatePoems,
  useDeletePoems,
  getListPoemsQueryKey,
} from "@/api/generated/admin/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { DataTable } from "@/components/DataTable";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { PoemAdminRead } from "@/api/generated/model";

export function PoemsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profileRaw } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const { data: raw } = useListPoems();
  const data = raw?.data;
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ content: "", order_index: 0 });

  const profileId = profileRaw?.data?.id ?? "";

  const create = useCreatePoems({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListPoemsQueryKey() }); setOpen(false); resetForm(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const update = useUpdatePoems({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListPoemsQueryKey() }); setEditingId(null); setOpen(false); resetForm(); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const del = useDeletePoems({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListPoemsQueryKey() }); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  function resetForm() {
    setForm({ content: "", order_index: 0 });
  }

  function startEdit(poem: PoemAdminRead) {
    setEditingId(poem.id);
    setForm({ content: poem.content, order_index: poem.order_index });
    setOpen(true);
  }

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); resetForm(); } }}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addPoem")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingId ? t("siteConfig.editPoem") : t("siteConfig.newPoem")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>{t("siteConfig.content")}</Label><Textarea value={form.content} onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))} rows={4} /></div>
              <div className="space-y-1"><Label>{t("common.order")}</Label><Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} /></div>
              <Button onClick={() => editingId ? update.mutate({ itemId: editingId, data: form }) : create.mutate({ data: { ...form, site_profile_id: profileId } })} disabled={create.isPending || update.isPending}>
                {editingId ? t("common.save") : t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        <DataTable<PoemAdminRead>
          columns={[
            { header: t("siteConfig.content"), accessor: (row) => <span className="line-clamp-2">{row.content}</span> },
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
