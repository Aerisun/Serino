import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listPageCopy,
  createPageCopy,
  updatePageCopy,
  deletePageCopy,
  listDisplayOptions,
  createDisplayOption,
  updateDisplayOption,
} from "@/api/endpoints/site-config";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { Plus, Save, Trash2, Pencil, X } from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { PAGE_KEYS, PAGE_KEY_LABELS, optionLabel } from "../constants";
import type { PageCopy, PageDisplayOption } from "@/types/models";

export function PagesTab() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const { data: copyData } = useQuery({
    queryKey: ["page-copy"],
    queryFn: () => listPageCopy(),
  });
  const { data: displayData } = useQuery({
    queryKey: ["display-options"],
    queryFn: () => listDisplayOptions(),
  });

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    page_key: "",
    title: "",
    subtitle: "",
    label: "",
    description: "",
    search_placeholder: "",
    empty_message: "",
    page_size: "" as string,
  });

  const createCopy = useMutation({
    mutationFn: () =>
      createPageCopy({
        page_key: createForm.page_key,
        title: createForm.title,
        subtitle: createForm.subtitle,
        label: createForm.label || null,
        description: createForm.description || null,
        search_placeholder: createForm.search_placeholder || null,
        empty_message: createForm.empty_message || null,
        page_size: createForm.page_size ? parseInt(createForm.page_size) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["page-copy"] });
      setCreateOpen(false);
      setCreateForm({
        page_key: "",
        title: "",
        subtitle: "",
        label: "",
        description: "",
        search_placeholder: "",
        empty_message: "",
        page_size: "",
      });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  // Merge copy + display by page_key
  const copies = copyData?.items ?? [];
  const displays = displayData?.items ?? [];
  const displayByKey = Object.fromEntries(displays.map((d) => [d.page_key, d]));

  const formFieldLabels: Record<string, string> = {
    title: t("common.title"),
    subtitle: t("siteConfig.subtitle"),
    label: `${t("siteConfig.label")} (${t("common.optional")})`,
    description: `${t("siteConfig.description2")} (${t("common.optional")})`,
    search_placeholder: `${t("siteConfig.searchPlaceholder")} (${t("common.optional")})`,
    empty_message: `${t("siteConfig.emptyMessage")} (${t("common.optional")})`,
  };

  return (
    <div className="mt-4 space-y-4">
      <div className="flex justify-end">
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addPage")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{t("siteConfig.newPageCopy")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>{t("siteConfig.pageKey")}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={createForm.page_key}
                  onChange={(e) =>
                    setCreateForm((p) => ({ ...p, page_key: e.target.value }))
                  }
                >
                  <option value="">{t("siteConfig.selectPage")}</option>
                  {PAGE_KEYS.map((k) => (
                    <option key={k} value={k}>
                      {optionLabel(PAGE_KEY_LABELS, k, lang)}
                    </option>
                  ))}
                </select>
              </div>
              {(
                [
                  "title",
                  "subtitle",
                  "label",
                  "description",
                  "search_placeholder",
                  "empty_message",
                ] as const
              ).map((k) => (
                <div key={k} className="space-y-1">
                  <Label>{formFieldLabels[k]}</Label>
                  <Input
                    value={createForm[k]}
                    onChange={(e) =>
                      setCreateForm((p) => ({ ...p, [k]: e.target.value }))
                    }
                  />
                </div>
              ))}
              <div className="space-y-1">
                <Label>{`${t("siteConfig.pageSize")} (${t("common.optional")})`}</Label>
                <Input
                  type="number"
                  value={createForm.page_size}
                  onChange={(e) =>
                    setCreateForm((p) => ({ ...p, page_size: e.target.value }))
                  }
                />
              </div>
              <Button
                onClick={() => createCopy.mutate()}
                disabled={createCopy.isPending || !createForm.page_key}
              >
                {t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {copies.length === 0 && displays.length === 0 && (
        <p className="text-muted-foreground py-4">{t("siteConfig.noPages")}</p>
      )}

      {copies.map((copy) => (
        <PageRow
          key={copy.id}
          copy={copy}
          display={displayByKey[copy.page_key]}
        />
      ))}
    </div>
  );
}

function PageRow({
  copy,
  display,
}: {
  copy: PageCopy;
  display?: PageDisplayOption;
}) {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    title: copy.title,
    subtitle: copy.subtitle,
    label: copy.label ?? "",
    description: copy.description ?? "",
    search_placeholder: copy.search_placeholder ?? "",
    empty_message: copy.empty_message ?? "",
    page_size: copy.page_size?.toString() ?? "",
  });
  const [settingsJson, setSettingsJson] = useState(
    display ? JSON.stringify(display.settings, null, 2) : "{}",
  );

  const saveCopy = useMutation({
    mutationFn: () =>
      updatePageCopy(copy.id, {
        title: form.title,
        subtitle: form.subtitle,
        label: form.label || null,
        description: form.description || null,
        search_placeholder: form.search_placeholder || null,
        empty_message: form.empty_message || null,
        page_size: form.page_size ? parseInt(form.page_size) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["page-copy"] });
      setEditing(false);
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  const toggleEnabled = useMutation({
    mutationFn: () => {
      if (display)
        return updateDisplayOption(display.id, {
          is_enabled: !display.is_enabled,
        });
      return createDisplayOption({ page_key: copy.page_key, is_enabled: true });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["display-options"] });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  const saveSettings = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(settingsJson);
      if (display) return updateDisplayOption(display.id, { settings: parsed });
      return createDisplayOption({ page_key: copy.page_key, settings: parsed });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["display-options"] });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  const delCopy = useMutation({
    mutationFn: () => deletePageCopy(copy.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["page-copy"] });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error: any) => {
      const msg = error?.response?.data?.detail || t("common.operationFailed");
      toast.error(msg);
    },
  });

  const formFieldLabels: Record<string, string> = {
    title: t("common.title"),
    subtitle: t("siteConfig.subtitle"),
    label: `${t("siteConfig.label")} (${t("common.optional")})`,
    description: `${t("siteConfig.description2")} (${t("common.optional")})`,
    search_placeholder: `${t("siteConfig.searchPlaceholder")} (${t("common.optional")})`,
    empty_message: `${t("siteConfig.emptyMessage")} (${t("common.optional")})`,
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base font-semibold">
          {optionLabel(PAGE_KEY_LABELS, copy.page_key, lang)}
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => toggleEnabled.mutate()}
          >
            {display?.is_enabled !== false
              ? t("siteConfig.enabled")
              : t("siteConfig.disabled")}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setEditing(!editing)}
          >
            {editing ? (
              <X className="h-4 w-4" />
            ) : (
              <Pencil className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              if (confirm(t("siteConfig.deletePageConfirm"))) delCopy.mutate();
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!editing ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <span className="text-muted-foreground">
                {t("common.title")}:
              </span>{" "}
              {copy.title}
            </div>
            <div>
              <span className="text-muted-foreground">
                {t("siteConfig.subtitle")}:
              </span>{" "}
              {copy.subtitle}
            </div>
            {copy.label && (
              <div>
                <span className="text-muted-foreground">
                  {t("siteConfig.label")}:
                </span>{" "}
                {copy.label}
              </div>
            )}
            {copy.description && (
              <div>
                <span className="text-muted-foreground">
                  {t("siteConfig.description2")}:
                </span>{" "}
                {copy.description}
              </div>
            )}
            {copy.search_placeholder && (
              <div>
                <span className="text-muted-foreground">
                  {t("siteConfig.searchPlaceholder")}:
                </span>{" "}
                {copy.search_placeholder}
              </div>
            )}
            {copy.empty_message && (
              <div>
                <span className="text-muted-foreground">
                  {t("siteConfig.emptyMessage")}:
                </span>{" "}
                {copy.empty_message}
              </div>
            )}
            {copy.page_size != null && (
              <div>
                <span className="text-muted-foreground">
                  {t("siteConfig.pageSize")}:
                </span>{" "}
                {copy.page_size}
              </div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              {(
                [
                  "title",
                  "subtitle",
                  "label",
                  "description",
                  "search_placeholder",
                  "empty_message",
                ] as const
              ).map((k) => (
                <div key={k} className="space-y-1">
                  <Label className="text-xs">{formFieldLabels[k]}</Label>
                  <Input
                    value={form[k]}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, [k]: e.target.value }))
                    }
                  />
                </div>
              ))}
              <div className="space-y-1">
                <Label className="text-xs">{`${t("siteConfig.pageSize")} (${t("common.optional")})`}</Label>
                <Input
                  type="number"
                  value={form.page_size}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, page_size: e.target.value }))
                  }
                />
              </div>
              <Button
                size="sm"
                onClick={() => saveCopy.mutate()}
                disabled={saveCopy.isPending}
              >
                <Save className="h-3 w-3 mr-1" /> {t("siteConfig.saveCopy")}
              </Button>
            </div>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label className="text-xs">
                  {t("siteConfig.settingsJson")}
                </Label>
                <Textarea
                  value={settingsJson}
                  onChange={(e) => setSettingsJson(e.target.value)}
                  rows={8}
                  className="font-mono text-xs"
                />
              </div>
              <Button
                size="sm"
                onClick={() => saveSettings.mutate()}
                disabled={saveSettings.isPending}
              >
                <Save className="h-3 w-3 mr-1" /> {t("siteConfig.saveSettings")}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
