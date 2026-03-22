import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listApiKeys, createApiKey, deleteApiKey } from "@/api/endpoints/system";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Plus, Trash2, Copy } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { ApiKey } from "@/types/models";

export default function ApiKeysPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [form, setForm] = useState({ key_name: "", scopes: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: listApiKeys,
  });

  const create = useMutation({
    mutationFn: () => createApiKey({ key_name: form.key_name, scopes: form.scopes ? form.scopes.split(",").map((s) => s.trim()) : [] }),
    onSuccess: (res) => {
      setRawKey(res.raw_key);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteApiKey(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["api-keys"] }); toast.success(t("common.operationSuccess")); },
    onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
  });

  return (
    <div>
      <PageHeader
        title={t("system.apiKeys")}
        description={t("system.apiKeysDescription")}
        actions={
          <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setRawKey(null); }}>
            <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("system.createKey")}</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>{rawKey ? t("system.keyCreated") : t("system.newApiKey")}</DialogTitle></DialogHeader>
              {rawKey ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">{t("system.copyKeyWarning")}</p>
                  <div className="flex gap-2">
                    <Input value={rawKey} readOnly className="font-mono text-xs" />
                    <Button variant="outline" size="icon" onClick={() => navigator.clipboard.writeText(rawKey)}><Copy className="h-4 w-4" /></Button>
                  </div>
                  <Button onClick={() => { setOpen(false); setRawKey(null); }}>{t("common.done")}</Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-1"><Label>{t("system.keyName")}</Label><Input value={form.key_name} onChange={(e) => setForm((p) => ({ ...p, key_name: e.target.value }))} /></div>
                  <div className="space-y-1"><Label>{t("system.scopesHint")}</Label><Input value={form.scopes} onChange={(e) => setForm((p) => ({ ...p, scopes: e.target.value }))} /></div>
                  <Button onClick={() => create.mutate()} disabled={create.isPending}>{t("common.create")}</Button>
                </div>
              )}
            </DialogContent>
          </Dialog>
        }
      />
      <div className="border rounded-lg">
        <DataTable<ApiKey>
          columns={[
            { header: t("common.name"), accessor: "key_name" },
            { header: t("common.prefix"), accessor: (row) => <code className="text-xs">{row.key_prefix}...</code> },
            { header: t("system.scopes"), accessor: (row) => row.scopes.join(", ") || "-" },
            { header: t("system.lastUsed"), accessor: (row) => formatDate(row.last_used_at) },
            { header: t("system.created"), accessor: (row) => formatDate(row.created_at) },
            { header: "", accessor: (row) => <Button variant="ghost" size="icon" onClick={() => { if (confirm(t("system.deleteConfirm"))) del.mutate(row.id); }}><Trash2 className="h-4 w-4" /></Button> },
          ]}
          data={data ?? []}
          total={data?.length ?? 0}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
