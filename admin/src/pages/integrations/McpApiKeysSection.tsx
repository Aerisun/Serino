import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { ApiKeyAdminRead } from "@serino/api-client/models";
import {
  getListApiKeysApiV1AdminIntegrationsApiKeysGetQueryKey,
  useCreateApiKeyApiV1AdminIntegrationsApiKeysPost,
  useDeleteApiKeyApiV1AdminIntegrationsApiKeysKeyIdDelete,
  useListApiKeysApiV1AdminIntegrationsApiKeysGet,
  useUpdateApiKeyApiV1AdminIntegrationsApiKeysKeyIdPut,
} from "@serino/api-client/admin";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import { formatDate } from "@/lib/utils";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  describeMcpPreset,
  detectMcpPreset,
  mergeMcpScopes,
  presetLabel,
  scopesForPreset,
  type McpKeyPreset,
} from "./mcpScopes";

export function McpApiKeysSection() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [sessionRawKeys, setSessionRawKeys] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<ApiKeyAdminRead | null>(null);
  const [form, setForm] = useState<{ key_name: string; preset: McpKeyPreset }>({
    key_name: "",
    preset: "readonly",
  });

  const { data: raw, isLoading } = useListApiKeysApiV1AdminIntegrationsApiKeysGet();
  const apiKeys = raw?.data as ApiKeyAdminRead[] | undefined;
  const mcpKeys = useMemo(
    () => (apiKeys ?? []).filter((item) => item.scopes.includes("mcp:connect")),
    [apiKeys],
  );

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: getListApiKeysApiV1AdminIntegrationsApiKeysGetQueryKey(),
    });

  const create = useCreateApiKeyApiV1AdminIntegrationsApiKeysPost({
    mutation: {
      onSuccess: async (response) => {
        await invalidate();
        setRawKey(response.data.raw_key);
        setSessionRawKeys((current) => ({
          ...current,
          [response.data.item.id]: response.data.raw_key,
        }));
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || t("common.operationFailed"));
      },
    },
  });

  const update = useUpdateApiKeyApiV1AdminIntegrationsApiKeysKeyIdPut({
    mutation: {
      onSuccess: async () => {
        await invalidate();
        setOpen(false);
        setEditing(null);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || t("common.operationFailed"));
      },
    },
  });

  const del = useDeleteApiKeyApiV1AdminIntegrationsApiKeysKeyIdDelete({
    mutation: {
      onSuccess: async () => {
        await invalidate();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || t("common.operationFailed"));
      },
    },
  });

  const resetDialog = () => {
    setOpen(false);
    setRawKey(null);
    setEditing(null);
    setForm({ key_name: "", preset: "readonly" });
  };

  const openCreate = () => {
    setEditing(null);
    setRawKey(null);
    setForm({ key_name: "", preset: "readonly" });
    setOpen(true);
  };

  const openEdit = (item: ApiKeyAdminRead) => {
    const detectedPreset = detectMcpPreset(item.scopes) ?? "readonly";
    setEditing(item);
    setRawKey(null);
    setForm({
      key_name: item.key_name,
      preset: detectedPreset,
    });
    setOpen(true);
  };

  const previewScopes = mergeMcpScopes(
    editing?.scopes ?? [],
    scopesForPreset(form.preset, editing?.scopes ?? []),
  );

  const saveKey = () => {
    const keyName = form.key_name.trim();
    if (!keyName) {
      toast.error(t("system.keyName"));
      return;
    }

    const scopes = mergeMcpScopes(
      editing?.scopes ?? [],
      scopesForPreset(form.preset, editing?.scopes ?? []),
    );
    if (editing) {
      update.mutate({
        keyId: editing.id,
        data: {
          key_name: keyName,
          scopes,
        },
      });
      return;
    }

    create.mutate({
      data: {
        key_name: keyName,
        scopes,
      },
    });
  };

  const pending = create.isPending || update.isPending;
  const editingPresetState = editing ? describeMcpPreset(editing.scopes) : null;
  const customPresetOptionLabel =
    editingPresetState?.basePreset != null
      ? `${t("integrations.mcpKeyCustom")} · ${presetLabel(t, editingPresetState.basePreset)}`
      : t("integrations.mcpKeyCustom");

  const buildMaskedKey = (prefix: string, suffix?: string | null) => {
    const normalizedPrefix = prefix.trim();
    const normalizedSuffix = (suffix ?? "").trim();

    if (!normalizedPrefix || !normalizedSuffix) {
      return t("integrations.unavailable");
    }

    const head = normalizedPrefix.slice(0, 4);
    return `${head}****${normalizedSuffix.slice(-3)}`;
  };

  const copyKeyValue = async (item: ApiKeyAdminRead) => {
    const sessionRawKey = sessionRawKeys[item.id];
    const valueToCopy = sessionRawKey ?? buildMaskedKey(item.key_prefix, item.key_suffix);

    try {
      await navigator.clipboard.writeText(valueToCopy);
      toast.success(
        sessionRawKey ? t("integrations.mcpKeyCopiedFull") : t("integrations.mcpKeyCopiedMasked"),
      );
    } catch {
      toast.error(t("common.operationFailed"));
    }
  };

  return (
    <AdminSurface
      eyebrow={t("integrations.mcp")}
      title={t("integrations.mcpKeys")}
      description={t("integrations.mcpKeysDescription")}
    >
      <div className="mb-4 flex items-center justify-between gap-3 rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/55 px-4 py-3">
        <div className="text-sm text-muted-foreground">{t("integrations.mcpKeysHint")}</div>
        <Dialog
          open={open}
          onOpenChange={(nextOpen) => {
            if (!nextOpen) {
              resetDialog();
              return;
            }
            setOpen(true);
          }}
        >
          <DialogTrigger asChild>
            <Button type="button" onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              {t("system.createKey")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg rounded-2xl">
            <DialogHeader className="text-left">
              <DialogTitle>
                {rawKey
                  ? t("system.keyCreated")
                  : editing
                    ? t("integrations.mcpEditKey")
                    : t("system.newApiKey")}
              </DialogTitle>
              <DialogDescription>
                {rawKey ? t("system.copyKeyWarning") : t("integrations.mcpKeyDialogDescription")}
              </DialogDescription>
            </DialogHeader>

            {rawKey ? (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Input value={rawKey} readOnly className="font-mono text-xs" />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => navigator.clipboard.writeText(rawKey)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <Button type="button" onClick={resetDialog}>
                  {t("common.done")}
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("system.keyName")}</Label>
                  <Input
                    value={form.key_name}
                    onChange={(event) => setForm((current) => ({ ...current, key_name: event.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <Label>{t("integrations.mcpKeyLevel")}</Label>
                  <Select
                    value={form.preset}
                    onValueChange={(value) => setForm((current) => ({ ...current, preset: value as McpKeyPreset }))}
                  >
                    <SelectTrigger className="h-11 rounded-xl border-border/50 bg-background/70">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="readonly">{t("integrations.mcpKeyReadonly")}</SelectItem>
                      <SelectItem value="basic_management">{t("integrations.mcpKeyBasic")}</SelectItem>
                      <SelectItem value="full_management">{t("integrations.mcpKeyFull")}</SelectItem>
                      {editing && form.preset === "custom" ? (
                        <SelectItem value="custom">{customPresetOptionLabel}</SelectItem>
                      ) : null}
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/55 px-4 py-4">
                  <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                    {t("system.scopes")}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {previewScopes.map((scope) => (
                      <Badge key={scope} variant="outline" className="font-mono">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="ghost" onClick={resetDialog}>
                    {t("common.cancel")}
                  </Button>
                  <Button type="button" onClick={saveKey} disabled={pending}>
                    {editing ? t("common.save") : t("common.create")}
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      <div className="overflow-hidden rounded-[var(--admin-radius-xl)]">
        <DataTable<ApiKeyAdminRead>
          columns={[
            { header: t("common.name"), accessor: "key_name" },
            {
              header: t("integrations.mcpKeyValue"),
              accessor: (row) => (
                <div className="flex items-center gap-2">
                  <code className="rounded-md bg-muted/50 px-2 py-1 font-mono text-xs">
                    {buildMaskedKey(row.key_prefix, row.key_suffix)}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    aria-label={t("integrations.copyMcpKey")}
                    onClick={(event) => {
                      event.stopPropagation();
                      void copyKeyValue(row);
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              ),
              className: "min-w-[14rem]",
            },
            {
              header: t("integrations.mcpKeyLevel"),
              accessor: (row) => {
                const presetState = describeMcpPreset(row.scopes);
                return (
                  <div className="flex flex-wrap gap-2">
                    {presetState.isCustom ? <Badge variant="warning">{t("integrations.mcpKeyCustom")}</Badge> : null}
                    <Badge variant={presetState.basePreset === "full_management" ? "info" : "outline"}>
                      {presetLabel(t, presetState.basePreset ?? "custom")}
                    </Badge>
                  </div>
                );
              },
            },
            { header: t("system.lastUsed"), accessor: (row) => formatDate(row.last_used_at) },
            {
              header: "",
              accessor: (row) => (
                <div className="flex justify-end gap-1">
                  <Button type="button" variant="ghost" size="icon" onClick={() => openEdit(row)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      if (confirm(t("system.deleteConfirm"))) {
                        del.mutate({ keyId: row.id });
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ),
              className: "w-[7rem]",
            },
          ]}
          data={mcpKeys}
          total={mcpKeys.length}
          isLoading={isLoading}
        />
      </div>
    </AdminSurface>
  );
}
