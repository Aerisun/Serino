import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListNavItems,
  useCreateNavItems,
  useUpdateNavItems,
  useDeleteNavItems,
  getListNavItemsQueryKey,
} from "@serino/api-client/admin";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { Plus, Trash2, Pencil } from "lucide-react";
import type { NavItemAdminRead } from "@serino/api-client/models";

export function NavItemsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: raw } = useListNavItems();
  const data = raw?.data;
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    label: "",
    href: "",
    trigger: "",
    page_key: "",
    parent_id: "",
    order_index: 0,
    is_enabled: true,
  });

  const items = data?.items ?? [];
  const topLevel = items
    .filter((i) => !i.parent_id)
    .sort((a, b) => a.order_index - b.order_index);
  const childrenOf = (pid: string) =>
    items
      .filter((i) => i.parent_id === pid)
      .sort((a, b) => a.order_index - b.order_index);

  const create = useCreateNavItems({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListNavItemsQueryKey() });
        setOpen(false);
        resetForm();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const update = useUpdateNavItems({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListNavItemsQueryKey() });
        setEditingId(null);
        setOpen(false);
        resetForm();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const del = useDeleteNavItems({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListNavItemsQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  function resetForm() {
    setForm({
      label: "",
      href: "",
      trigger: "",
      page_key: "",
      parent_id: "",
      order_index: 0,
      is_enabled: true,
    });
  }

  function startEdit(item: NavItemAdminRead) {
    setEditingId(item.id);
    setForm({
      label: item.label,
      href: item.href,
      trigger: item.trigger || "",
      page_key: item.page_key || "",
      parent_id: item.parent_id || "",
      order_index: item.order_index,
      is_enabled: item.is_enabled,
    });
    setOpen(true);
  }

  function renderItem(item: NavItemAdminRead, depth: number = 0) {
    const children = childrenOf(item.id);
    return (
      <div key={item.id}>
        <div
          className={`flex items-center gap-2 py-2 px-3 border-b hover:bg-muted/50 ${depth > 0 ? "pl-8" : ""}`}
        >
          <span
            className={`text-sm font-medium ${!item.is_enabled ? "text-muted-foreground line-through" : ""}`}
          >
            {item.label}
          </span>
          <span className="text-xs text-muted-foreground">{item.href}</span>
          {item.trigger && (
            <span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 rounded">
              {item.trigger}
            </span>
          )}
          {item.page_key && (
            <span className="text-xs bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 px-1.5 rounded">
              {item.page_key}
            </span>
          )}
          <span className="text-xs text-muted-foreground ml-auto">
            #{item.order_index}
          </span>
          <Button variant="ghost" size="icon" onClick={() => startEdit(item)}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => del.mutate({ itemId: item.id })}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
        {children.map((c) => renderItem(c, depth + 1))}
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog
          open={open}
          onOpenChange={(v) => {
            setOpen(v);
            if (!v) {
              setEditingId(null);
              resetForm();
            }
          }}
        >
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" /> {t("navItems.add")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingId ? t("navItems.edit") : t("navItems.create")}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>{t("navItems.label")}</Label>
                <Input
                  value={form.label}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, label: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>{t("navItems.href")}</Label>
                <Input
                  value={form.href}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, href: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>
                  {t("navItems.trigger")} ({t("common.optional")})
                </Label>
                <Input
                  value={form.trigger}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, trigger: e.target.value }))
                  }
                  placeholder={t("navItems.triggerPlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>
                  {t("navItems.pageKey")} ({t("common.optional")})
                </Label>
                <Input
                  value={form.page_key}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, page_key: e.target.value }))
                  }
                  placeholder={t("navItems.pageKeyPlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>
                  {t("navItems.parent")} ({t("common.optional")})
                </Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.parent_id}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, parent_id: e.target.value }))
                  }
                >
                  <option value="">{t("navItems.parentNone")}</option>
                  {items
                    .filter((i) => !i.parent_id && i.id !== editingId)
                    .map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.label}
                      </option>
                    ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label>{t("navItems.order")}</Label>
                <Input
                  type="number"
                  value={form.order_index}
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      order_index: parseInt(e.target.value) || 0,
                    }))
                  }
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_enabled}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, is_enabled: e.target.checked }))
                  }
                />
                <Label>{t("navItems.enabled")}</Label>
              </div>
              <Button
                onClick={() => {
                  const payload = {
                    ...form,
                    trigger: form.trigger || null,
                    page_key: form.page_key || null,
                    parent_id: form.parent_id || null,
                  };

                  if (editingId) {
                    update.mutate({ itemId: editingId, data: payload });
                    return;
                  }

                  create.mutate({ data: payload });
                }}
                disabled={create.isPending || update.isPending}
              >
                {editingId ? t("navItems.save") : t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        {topLevel.length === 0 && (
          <p className="p-4 text-muted-foreground text-sm">
            {t("navItems.empty")}
          </p>
        )}
        {topLevel.map((item) => renderItem(item))}
      </div>
    </div>
  );
}
