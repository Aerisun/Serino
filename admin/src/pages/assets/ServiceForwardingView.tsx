import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ExternalLink, Pencil, PlugZap, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import {
  createServiceForward,
  deleteServiceForward,
  listServiceForwards,
  testServiceForward,
  updateServiceForward,
  type ServiceForwardRead,
  type ServiceForwardSource,
  type ServiceForwardWrite,
} from "@/pages/assets/serviceForwardApi";

interface ServiceForwardingViewProps {
  createOpen: boolean;
  onCreateOpenChange: (open: boolean) => void;
}

interface ServiceForwardDraft {
  name: string;
  slug: string;
  source: ServiceForwardSource;
  port: string;
  targetUrl: string;
}

const serviceForwardsQueryKey = ["admin", "service-forwards"] as const;

function emptyDraft(): ServiceForwardDraft {
  return {
    name: "",
    slug: "",
    source: "local",
    port: "3000",
    targetUrl: "",
  };
}

function localPortFromTargetUrl(targetUrl: string): string {
  try {
    const parsed = new URL(targetUrl);
    return parsed.port || (parsed.protocol === "https:" ? "443" : "80");
  } catch {
    return "3000";
  }
}

function draftFromRule(rule: ServiceForwardRead): ServiceForwardDraft {
  return {
    name: rule.name,
    slug: rule.slug,
    source: rule.source === "tailscale" ? "tailscale" : "local",
    port: rule.source === "local" ? localPortFromTargetUrl(rule.target_url) : "3000",
    targetUrl: rule.source === "tailscale" ? rule.target_url : "",
  };
}

export function ServiceForwardingView({
  createOpen,
  onCreateOpenChange,
}: ServiceForwardingViewProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<ServiceForwardRead | null>(null);
  const [deleting, setDeleting] = useState<ServiceForwardRead | null>(null);
  const [draft, setDraft] = useState<ServiceForwardDraft>(emptyDraft);
  const formOpen = createOpen || editing !== null;

  const { data = [], isLoading, isError, refetch } = useQuery({
    queryKey: serviceForwardsQueryKey,
    queryFn: listServiceForwards,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (createOpen && editing === null) {
      setDraft(emptyDraft());
    }
  }, [createOpen, editing]);

  const save = useMutation({
    mutationFn: (payload: ServiceForwardWrite) =>
      editing ? updateServiceForward(editing.id, payload) : createServiceForward(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: serviceForwardsQueryKey });
      toast.success(t(editing ? "serviceForwards.updated" : "serviceForwards.created"));
      if (editing) {
        setEditing(null);
      } else {
        onCreateOpenChange(false);
      }
    },
    onError: (error) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const probe = useMutation({
    mutationFn: (routeId: string) => testServiceForward(routeId),
    onSuccess: (result) => {
      queryClient.setQueryData<ServiceForwardRead[]>(serviceForwardsQueryKey, (current = []) =>
        current.map((rule) => (rule.id === result.id ? result : rule)),
      );
      if (result.status === "reachable") {
        toast.success(t("serviceForwards.testReachable"));
      } else {
        toast.error(result.status_message || t("serviceForwards.testUnreachable"));
      }
    },
    onError: (error) => {
      toast.error(extractApiErrorMessage(error, t("serviceForwards.testFailed")));
    },
  });

  const remove = useMutation({
    mutationFn: (routeId: string) => deleteServiceForward(routeId),
    onSuccess: async () => {
      setDeleting(null);
      await queryClient.invalidateQueries({ queryKey: serviceForwardsQueryKey });
      toast.success(t("serviceForwards.deleted"));
    },
    onError: (error) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const closeForm = () => {
    if (editing) {
      setEditing(null);
    } else {
      onCreateOpenChange(false);
    }
  };

  const startEditing = (rule: ServiceForwardRead) => {
    setDraft(draftFromRule(rule));
    setEditing(rule);
  };

  const submit = () => {
    const normalizedSlug = draft.slug.trim().toLowerCase().replace(/^\/+|\/+$/g, "");
    if (!draft.name.trim() || !normalizedSlug) {
      toast.error(t("serviceForwards.requiredFields"));
      return;
    }
    const commonPayload = {
      name: draft.name.trim(),
      slug: normalizedSlug,
      source: draft.source,
    };
    if (draft.source === "local") {
      const port = Number(draft.port);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        toast.error(t("serviceForwards.invalidPort"));
        return;
      }
      save.mutate({ ...commonPayload, source: "local", port });
      return;
    }

    const targetUrl = draft.targetUrl.trim();
    try {
      const parsed = new URL(targetUrl);
      if (!parsed.hostname || !["http:", "https:"].includes(parsed.protocol)) {
        throw new Error("unsupported URL");
      }
    } catch {
      toast.error(t("serviceForwards.invalidTargetUrl"));
      return;
    }
    save.mutate({ ...commonPayload, source: "tailscale", target_url: targetUrl });
  };

  const statusBadge = (rule: ServiceForwardRead) => {
    if (rule.status === "reachable") {
      return (
        <Badge variant="success" title={rule.status_message || undefined}>
          {t("serviceForwards.reachable")}
        </Badge>
      );
    }
    if (rule.status === "unreachable") {
      return (
        <Badge variant="destructive" title={rule.status_message || undefined}>
          {t("serviceForwards.unreachable")}
        </Badge>
      );
    }
    return <Badge variant="secondary">{t("serviceForwards.unchecked")}</Badge>;
  };

  return (
    <div className="space-y-3">
      {isError ? (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-lg border border-destructive/25 bg-destructive/[0.05] p-4 text-sm sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-start gap-3 text-destructive">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{t("serviceForwards.loadFailed")}</span>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void refetch()}>
            {t("serviceForwards.reload")}
          </Button>
        </div>
      ) : (
        <DataTable<ServiceForwardRead>
          tableClassName="min-w-[48rem] table-fixed"
          columns={[
          {
            header: t("serviceForwards.name"),
            className: "w-[10rem] min-w-[10rem]",
            accessor: (rule) => (
              <div className="min-w-0">
                <div className="truncate font-medium" title={rule.name}>
                  {rule.name}
                </div>
              </div>
            ),
          },
          {
            header: t("serviceForwards.publicPath"),
            className: "w-[11rem] min-w-[11rem]",
            accessor: (rule) => (
              <a
                href={rule.path}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={t("serviceForwards.open")}
                title={rule.path}
                className="group inline-flex max-w-full items-center gap-1 rounded-md text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <code
                  className="min-w-0 truncate rounded bg-muted/55 px-2 py-1 text-xs transition-colors group-hover:bg-primary/10"
                >
                  {rule.path}
                </code>
                <ExternalLink className="h-4 w-4 shrink-0" />
              </a>
            ),
          },
          {
            header: t("serviceForwards.target"),
            className: "w-[16rem] min-w-[16rem]",
            accessor: (rule) => (
              <div
                className="truncate font-mono text-xs text-foreground/80"
                title={rule.target_url}
              >
                {rule.target_url}
              </div>
            ),
          },
          {
            header: t("serviceForwards.status"),
            className: "w-[6rem] min-w-[6rem]",
            accessor: statusBadge,
          },
          {
            header: t("common.actions"),
            className: "w-[9rem] min-w-[9rem] text-center",
            accessor: (rule) => (
              <div className="flex items-center justify-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 min-h-8 w-8"
                  aria-label={t("serviceForwards.test")}
                  disabled={probe.isPending && probe.variables === rule.id}
                  onClick={() => probe.mutate(rule.id)}
                >
                  <PlugZap className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 min-h-8 w-8"
                  aria-label={t("common.edit")}
                  disabled={rule.source === "custom"}
                  title={
                    rule.source === "custom" ? t("serviceForwards.customEditHint") : undefined
                  }
                  onClick={() => startEditing(rule)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 min-h-8 w-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                  aria-label={t("common.delete")}
                  onClick={() => setDeleting(rule)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ),
          },
          ]}
          data={data}
          total={data.length}
          isLoading={isLoading}
        />
      )}

      <Dialog open={formOpen} onOpenChange={(open) => !open && closeForm()}>
        <DialogContent aria-describedby={undefined} className="max-w-xl rounded-2xl">
          <DialogHeader className="pb-4 text-left">
            <DialogTitle>
              {t(editing ? "serviceForwards.editTitle" : "serviceForwards.addTitle")}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="service-forward-name">{t("serviceForwards.name")}</Label>
                <Input
                  id="service-forward-name"
                  value={draft.name}
                  maxLength={80}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, name: event.target.value }))
                  }
                  placeholder={t("serviceForwards.namePlaceholder")}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="service-forward-slug">{t("serviceForwards.slug")}</Label>
                <Input
                  id="service-forward-slug"
                  value={draft.slug}
                  maxLength={255}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      slug: event.target.value.toLowerCase().replace(/[^a-z0-9./-]/g, ""),
                    }))
                  }
                  placeholder="model/embedding/v1"
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="service-forward-source">{t("serviceForwards.source")}</Label>
                <NativeSelect
                  id="service-forward-source"
                  value={draft.source}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      source: event.target.value as ServiceForwardSource,
                    }))
                  }
                >
                  <option value="local">{t("serviceForwards.source.local")}</option>
                  <option value="tailscale">{t("serviceForwards.source.tailscale")}</option>
                </NativeSelect>
              </div>
              {draft.source === "local" ? (
                <div className="grid gap-2">
                  <Label htmlFor="service-forward-port">{t("serviceForwards.port")}</Label>
                  <Input
                    id="service-forward-port"
                    type="number"
                    min={1}
                    max={65535}
                    value={draft.port}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, port: event.target.value }))
                    }
                  />
                </div>
              ) : (
                <div className="grid gap-2">
                  <Label htmlFor="service-forward-target-url">
                    {t("serviceForwards.targetUrl")}
                  </Label>
                  <Input
                    id="service-forward-target-url"
                    type="url"
                    value={draft.targetUrl}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, targetUrl: event.target.value }))
                    }
                    placeholder={t("serviceForwards.targetUrlPlaceholder")}
                  />
                </div>
              )}
            </div>

            <div aria-hidden="true" className="h-10" />

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={closeForm} disabled={save.isPending}>
                {t("common.cancel")}
              </Button>
              <Button type="button" onClick={submit} disabled={save.isPending}>
                {save.isPending
                  ? t("common.saving")
                  : t(editing ? "common.save" : "serviceForwards.create")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        title={t("serviceForwards.deleteTitle")}
        description={
          deleting
            ? t("serviceForwards.deleteDescription", { name: deleting.name })
            : undefined
        }
        confirmLabel={t("serviceForwards.confirmDelete")}
        variant="destructive"
        isPending={remove.isPending}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </div>
  );
}
