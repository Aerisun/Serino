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
import {
  ActivationToggleButton,
  inactiveRowClassName,
} from "@/components/ActivationState";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
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
import { cn, formatDate } from "@/lib/utils";
import { extractApiErrorMessage } from "@/lib/api-error";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  CONNECT_SCOPE,
  describeMcpPreset,
  detectMcpPreset,
  mergeMcpScopes,
  presetLabel,
  scopesForPreset,
  type McpKeyPreset,
} from "./mcpScopes";

interface McpApiKeysSectionProps {
  disabled?: boolean;
}

export function McpApiKeysSection({ disabled = false }: McpApiKeysSectionProps) {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rawKey, setRawKey] = useState<string | null>(null);
  const [editing, setEditing] = useState<ApiKeyAdminRead | null>(null);
  const [form, setForm] = useState<{ key_name: string; preset: McpKeyPreset }>({
    key_name: "",
    preset: "readonly",
  });

  const { data: raw, isLoading } = useListApiKeysApiV1AdminIntegrationsApiKeysGet();
  const apiKeys = raw?.data as ApiKeyAdminRead[] | undefined;
  const mcpKeys = useMemo(
    () => (apiKeys ?? []).filter((item) => item.scopes.includes(CONNECT_SCOPE)),
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
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const toggleKey = useUpdateApiKeyApiV1AdminIntegrationsApiKeysKeyIdPut({
    mutation: {
      onSuccess: async () => {
        await invalidate();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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

  return (
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
      <AdminSurface
        eyebrow={t("integrations.mcp")}
        title={t("integrations.mcpKeys")}
        titleAccessory={
          <LabelWithHelp
            label={t("integrations.mcpKeys")}
            title={t("integrations.mcpKeys")}
            description={t("integrations.mcpKeysDescription")}
            usageTitle={lang === "zh" ? "用途" : "Usage"}
            usageItems={[t("integrations.mcpKeysHint")]}
            hideLabel
            className="gap-0"
          />
        }
        className={cn(disabled && "opacity-55")}
        actions={
          <DialogTrigger asChild>
            <Button type="button" onClick={openCreate} disabled={disabled}>
              <Plus className="mr-2 h-4 w-4" />
              {t("system.createKey")}
            </Button>
          </DialogTrigger>
        }
      >
        <div className={cn("overflow-hidden rounded-[var(--admin-radius-xl)]", disabled && "pointer-events-none")}>
          <DataTable<ApiKeyAdminRead>
            columns={[
              { header: t("common.name"), accessor: "key_name", className: "text-center" },
              {
                header: t("integrations.mcpKeyValue"),
                accessor: (row) => (
                  <code
                    className={cn(
                      "rounded-md bg-muted/50 px-2 py-1 font-mono text-xs",
                      !row.enabled && "bg-muted/35 text-muted-foreground",
                    )}
                  >
                    {buildMaskedKey(row.key_prefix, row.key_suffix)}
                  </code>
                ),
                className: "min-w-[10rem] text-center",
              },
              {
                header: t("integrations.mcpKeyLevel"),
                accessor: (row) => {
                  const presetState = describeMcpPreset(row.scopes);
                  return (
                    <div className="flex flex-wrap justify-center gap-2">
                      {presetState.isCustom ? (
                        <Badge
                          variant={row.enabled ? "warning" : "secondary"}
                          className={cn(!row.enabled && "border-border/40 bg-muted/35 text-muted-foreground")}
                        >
                          {t("integrations.mcpKeyCustom")}
                        </Badge>
                      ) : null}
                      <Badge
                        variant={row.enabled ? (presetState.basePreset === "full_management" ? "info" : "outline") : "secondary"}
                        className={cn(!row.enabled && "border-border/40 bg-muted/35 text-muted-foreground")}
                      >
                        {presetLabel(t, presetState.basePreset ?? "custom")}
                      </Badge>
                    </div>
                  );
                },
                className: "text-center",
              },
              {
                header: t("system.lastUsed"),
                accessor: (row) => formatDate(row.last_used_at),
                className: "text-center",
              },
              {
                header: t("common.actions"),
                accessor: (row) => (
                  <div className="flex items-center justify-center gap-1.5">
                    <ActivationToggleButton
                      isActive={row.enabled}
                      disabled={toggleKey.isPending}
                      activeLabel={t("integrations.enabled")}
                      inactiveLabel={t("integrations.disabled")}
                      activeTitle={t("integrations.enabled")}
                      inactiveTitle={t("integrations.disabled")}
                      onClick={() =>
                        toggleKey.mutate({
                          keyId: row.id,
                          data: {
                            enabled: !row.enabled,
                          },
                        })
                      }
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className={cn("min-h-0 h-8 w-8", !row.enabled && "text-muted-foreground")}
                      onClick={() => openEdit(row)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className={cn("min-h-0 h-8 w-8", !row.enabled && "text-muted-foreground")}
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
                className: "w-[12rem] text-center",
              },
            ]}
            data={mcpKeys}
            total={mcpKeys.length}
            isLoading={isLoading}
            getRowClassName={(row) => inactiveRowClassName(row.enabled)}
          />
        </div>
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
      </AdminSurface>
    </Dialog>
  );
}
