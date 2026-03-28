import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey,
  useDeleteWebhookApiV1AdminAutomationWebhooksSubscriptionIdDelete,
  useGetWebhooksApiV1AdminAutomationWebhooksGet,
  usePostWebhookApiV1AdminAutomationWebhooksPost,
  usePutWebhookApiV1AdminAutomationWebhooksSubscriptionIdPut,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { Plus, Trash2, Pencil } from "lucide-react";
import type { WebhookSubscriptionRead } from "@serino/api-client/models";

const WEBHOOK_STATUS_OPTIONS = ["active", "paused", "disabled"] as const;

export default function WebhooksPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<WebhookSubscriptionRead | null>(null);
  const [form, setForm] = useState({
    name: "",
    target_url: "",
    event_types: "comment.pending",
    secret: "",
    status: "active",
    timeout_seconds: "10",
    max_attempts: "6",
    headers: "{}",
  });
  const { data: raw, isLoading } = useGetWebhooksApiV1AdminAutomationWebhooksGet();
  const items = (raw?.data ?? []) as WebhookSubscriptionRead[];

  const resetForm = () => setForm({
    name: "",
    target_url: "",
    event_types: "comment.pending",
    secret: "",
    status: "active",
    timeout_seconds: "10",
    max_attempts: "6",
    headers: "{}",
  });

  const createWebhook = usePostWebhookApiV1AdminAutomationWebhooksPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        setOpen(false);
        setEditing(null);
        resetForm();
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const updateWebhook = usePutWebhookApiV1AdminAutomationWebhooksSubscriptionIdPut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        setOpen(false);
        setEditing(null);
        resetForm();
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const deleteWebhook = useDeleteWebhookApiV1AdminAutomationWebhooksSubscriptionIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetWebhooksApiV1AdminAutomationWebhooksGetQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const openCreate = () => {
    setEditing(null);
    resetForm();
    setOpen(true);
  };

  const openEdit = (row: WebhookSubscriptionRead) => {
    setEditing(row);
    setForm({
      name: row.name,
      target_url: row.target_url,
      event_types: row.event_types.join(", "),
      secret: row.secret ?? "",
      status: row.status,
      timeout_seconds: String(row.timeout_seconds ?? 10),
      max_attempts: String(row.max_attempts ?? 6),
      headers: JSON.stringify(row.headers ?? {}, null, 2),
    });
    setOpen(true);
  };

  const submit = () => {
    let parsedHeaders: Record<string, string> = {};
    try {
      parsedHeaders = JSON.parse(form.headers || "{}");
    } catch {
      toast.error("Headers 必须是合法 JSON");
      return;
    }

    const payload = {
      ...form,
      event_types: form.event_types.split(",").map((s) => s.trim()).filter(Boolean),
      timeout_seconds: Number(form.timeout_seconds || 10),
      max_attempts: Number(form.max_attempts || 6),
      headers: parsedHeaders,
    };
    if (editing) {
      updateWebhook.mutate({ subscriptionId: editing.id, data: payload });
      return;
    }
    createWebhook.mutate({ data: payload });
  };

  return (
    <div>
      <PageHeader
        title={t("automation.webhooks")}
        description={t("automation.webhooksDescription")}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button onClick={openCreate}><Plus className="mr-2 h-4 w-4" />{t("common.create")}</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>{editing ? t("common.edit") : t("common.create")}</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div className="space-y-1"><Label>Name</Label><Input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></div>
                <div className="space-y-1"><Label>Target URL</Label><Input value={form.target_url} onChange={(e) => setForm((p) => ({ ...p, target_url: e.target.value }))} /></div>
                <div className="space-y-1"><Label>Events</Label><Input value={form.event_types} onChange={(e) => setForm((p) => ({ ...p, event_types: e.target.value }))} /></div>
                <div className="space-y-1"><Label>Secret</Label><Input value={form.secret} onChange={(e) => setForm((p) => ({ ...p, secret: e.target.value }))} /></div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label>Status</Label>
                    <Select value={form.status} onValueChange={(value) => setForm((p) => ({ ...p, status: value }))}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select status" />
                      </SelectTrigger>
                      <SelectContent>
                        {WEBHOOK_STATUS_OPTIONS.map((status) => (
                          <SelectItem key={status} value={status}>{status}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1"><Label>Timeout (seconds)</Label><Input type="number" min="1" value={form.timeout_seconds} onChange={(e) => setForm((p) => ({ ...p, timeout_seconds: e.target.value }))} /></div>
                </div>
                <div className="space-y-1"><Label>Max Attempts</Label><Input type="number" min="1" value={form.max_attempts} onChange={(e) => setForm((p) => ({ ...p, max_attempts: e.target.value }))} /></div>
                <div className="space-y-1">
                  <Label>Headers (JSON)</Label>
                  <Textarea
                    className="min-h-32"
                    value={form.headers}
                    onChange={(e) => setForm((p) => ({ ...p, headers: e.target.value }))}
                  />
                </div>
                <Button onClick={submit} disabled={createWebhook.isPending || updateWebhook.isPending}>{editing ? t("common.save") : t("common.create")}</Button>
              </div>
            </DialogContent>
          </Dialog>
        }
      />
      <AdminSurface eyebrow="Webhook" title={t("automation.webhooks")} description={t("automation.webhooksDescription")}>
        <DataTable
          columns={[
            { header: t("common.name"), accessor: "name" },
            { header: "URL", accessor: (row) => <code className="text-xs break-all">{row.target_url}</code> },
            { header: "Events", accessor: (row) => row.event_types.join(", ") || "-" },
            { header: "Timeout", accessor: (row) => row.timeout_seconds },
            { header: "Attempts", accessor: (row) => row.max_attempts },
            { header: t("automation.status"), accessor: (row) => <Badge variant="outline">{row.status}</Badge> },
            {
              header: t("common.actions"),
              accessor: (row) => (
                <div className="flex gap-2">
                  <Button variant="ghost" size="icon" onClick={() => openEdit(row)}><Pencil className="h-4 w-4" /></Button>
                  <Button variant="ghost" size="icon" onClick={() => deleteWebhook.mutate({ subscriptionId: row.id })}><Trash2 className="h-4 w-4" /></Button>
                </div>
              ),
            },
          ]}
          data={items}
          isLoading={isLoading}
        />
      </AdminSurface>
    </div>
  );
}
