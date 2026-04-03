import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListPageCopy,
  useCreatePageCopy,
  useUpdatePageCopy,
  useDeletePageCopy,
  useListDisplayOptions,
  useCreateDisplayOptions,
  useUpdateDisplayOptions,
  getListPageCopyQueryKey,
  getListDisplayOptionsQueryKey,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import { PAGE_KEYS, PAGE_KEY_LABELS, optionLabel } from "../constants";
import type {
  PageCopyAdminRead,
  PageDisplayOptionAdminRead,
} from "@serino/api-client/models";
import {
  type PageFieldDefinition,
  WIDTH_OPTIONS,
  getFieldsForPage,
} from "../page-field-defs";

type PageFormState = Record<string, string> & { page_key: string };

const emptyCreateForm = (): PageFormState => ({ page_key: "" });

const readFieldValue = (
  copy: Pick<PageCopyAdminRead, "extras"> & Record<string, unknown>,
  field: PageFieldDefinition,
) => {
  if (field.source === "base") {
    const raw = copy[field.key];
    return raw == null ? "" : String(raw);
  }

  const raw = copy.extras?.[field.key];
  if (Array.isArray(raw)) {
    return raw.map(String).join("\n");
  }
  if (raw == null) {
    return "";
  }
  return String(raw);
};

const buildFormState = (pageKey: string, copy?: PageCopyAdminRead): PageFormState => {
  const state: PageFormState = { page_key: pageKey };
  for (const field of getFieldsForPage(pageKey)) {
    state[field.key] = copy ? readFieldValue(copy as PageCopyAdminRead & Record<string, unknown>, field) : "";
  }
  return state;
};

const normalizeOptionalText = (value: string) => {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const parseOptionalNumber = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
};

const parseListValue = (value: string) =>
  value
    .split(/\n|,/g)
    .map((item) => item.trim())
    .filter(Boolean);

const assignExtraValue = (
  target: Record<string, unknown>,
  field: PageFieldDefinition,
  rawValue: string,
) => {
  if (field.input === "list") {
    const items = parseListValue(rawValue);
    if (items.length > 0) {
      target[field.key] = items;
    } else {
      delete target[field.key];
    }
    return;
  }

  if (field.input === "number") {
    const parsed = parseOptionalNumber(rawValue);
    if (parsed != null) {
      target[field.key] = parsed;
    } else {
      delete target[field.key];
    }
    return;
  }

  const normalized = normalizeOptionalText(rawValue);
  if (normalized != null) {
    target[field.key] = normalized;
  } else {
    delete target[field.key];
  }
};

const buildCopyPayload = (
  pageKey: string,
  form: PageFormState,
  existingExtras?: Record<string, unknown>,
  includePageKey = false,
) => {
  const extras = { ...(existingExtras ?? {}) };

  for (const field of getFieldsForPage(pageKey)) {
    if (field.source === "extra") {
      assignExtraValue(extras, field, form[field.key] ?? "");
    }
  }

  return {
    ...(includePageKey ? { page_key: pageKey } : {}),
    title: (form.title ?? "").trim(),
    subtitle: (form.subtitle ?? "").trim(),
    description: normalizeOptionalText(form.description ?? ""),
    search_placeholder: normalizeOptionalText(form.search_placeholder ?? ""),
    empty_message: normalizeOptionalText(form.empty_message ?? ""),
    max_width: normalizeOptionalText(form.max_width ?? ""),
    page_size: parseOptionalNumber(form.page_size ?? ""),
    download_label: normalizeOptionalText(form.download_label ?? ""),
    extras,
  };
};

const renderFieldValue = (copy: PageCopyAdminRead, field: PageFieldDefinition) => {
  if (field.source === "base") {
    const raw = copy[field.key as keyof PageCopyAdminRead];
    if (raw == null || raw === "") {
      return null;
    }
    if (field.key === "max_width") {
      const match = WIDTH_OPTIONS.find((option) => option.value === raw);
      return match?.label ?? String(raw);
    }
    return String(raw);
  }

  const raw = copy.extras?.[field.key];
  if (raw == null || raw === "") {
    return null;
  }
  if (Array.isArray(raw)) {
    return raw.join(" / ");
  }
  return String(raw);
};

const renderFieldInput = (
  field: PageFieldDefinition,
  value: string,
  onChange: (nextValue: string) => void,
) => {
  if (field.input === "textarea" || field.input === "list") {
    return (
      <Textarea
        value={value}
        rows={field.input === "list" ? 4 : 3}
        placeholder={field.placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  if (field.input === "select") {
    return (
      <select
        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {(field.options ?? []).map((option) => (
          <option key={option.value || "empty"} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <Input
      type={field.input === "number" ? "number" : "text"}
      value={value}
      placeholder={field.placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
};

export function PagesTab() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const { data: copyRaw } = useListPageCopy();
  const { data: displayRaw } = useListDisplayOptions();
  const copies = useMemo(() => copyRaw?.data?.items ?? [], [copyRaw]);
  const displays = useMemo(() => displayRaw?.data?.items ?? [], [displayRaw]);
  const displayByKey = Object.fromEntries(displays.map((item) => [item.page_key, item]));
  const orderedCopies = useMemo(
    () =>
      [...copies].sort(
        (left, right) => PAGE_KEYS.indexOf(left.page_key) - PAGE_KEYS.indexOf(right.page_key),
      ),
    [copies],
  );

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<PageFormState>(emptyCreateForm());
  const createFields = createForm.page_key ? getFieldsForPage(createForm.page_key) : [];

  const resetCreateForm = () => setCreateForm(emptyCreateForm());

  const createCopy = useCreatePageCopy({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListPageCopyQueryKey() });
        setCreateOpen(false);
        resetCreateForm();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  return (
    <div className="mt-4 space-y-4">
      <div className="flex justify-end">
        <Dialog
          open={createOpen}
          onOpenChange={(nextOpen) => {
            setCreateOpen(nextOpen);
            if (!nextOpen) {
              resetCreateForm();
            }
          }}
        >
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              {t("siteConfig.addPage")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>{t("siteConfig.newPageCopy")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-1">
                <Label>选择页面</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={createForm.page_key}
                  onChange={(event) => {
                    const pageKey = event.target.value;
                    setCreateForm(pageKey ? buildFormState(pageKey) : emptyCreateForm());
                  }}
                >
                  <option value="">{t("siteConfig.selectPage")}</option>
                  {PAGE_KEYS.map((pageKey) => (
                    <option key={pageKey} value={pageKey}>
                      {optionLabel(PAGE_KEY_LABELS, pageKey, lang)}
                    </option>
                  ))}
                </select>
              </div>

              {createFields.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {createFields.map((field) => (
                    <div key={field.key} className={field.input === "textarea" || field.input === "list" ? "md:col-span-2 space-y-1" : "space-y-1"}>
                      <LabelWithHelp
                        label={field.optional ? `${field.label}（可选）` : field.label}
                        title={field.helpTitle}
                        description={field.helpDescription}
                        usageTitle="会影响这些位置"
                        usageItems={field.usageItems}
                      />
                      {renderFieldInput(field, createForm[field.key] ?? "", (nextValue) =>
                        setCreateForm((current) => ({ ...current, [field.key]: nextValue })),
                      )}
                    </div>
                  ))}
                </div>
              ) : null}

              <Button
                onClick={() =>
                  createCopy.mutate({
                    data: buildCopyPayload(createForm.page_key, createForm, undefined, true),
                  })
                }
                disabled={
                  createCopy.isPending ||
                  !createForm.page_key ||
                  !(createForm.title ?? "").trim() ||
                  !(createForm.subtitle ?? "").trim()
                }
              >
                {t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {orderedCopies.length === 0 && displays.length === 0 ? (
        <p className="py-4 text-muted-foreground">{t("siteConfig.noPages")}</p>
      ) : null}

      {orderedCopies.map((copy) => (
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
  copy: PageCopyAdminRead;
  display?: PageDisplayOptionAdminRead;
}) {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<PageFormState>(() => buildFormState(copy.page_key, copy));
  const [settingsJson, setSettingsJson] = useState(
    display ? JSON.stringify(display.settings, null, 2) : "{}",
  );
  const fields = getFieldsForPage(copy.page_key);

  const saveCopy = useUpdatePageCopy({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListPageCopyQueryKey() });
        setEditing(false);
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const toggleEnabled = useUpdateDisplayOptions({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListDisplayOptionsQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const createDisplayOpt = useCreateDisplayOptions({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListDisplayOptionsQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const saveSettings = useUpdateDisplayOptions({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListDisplayOptionsQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const delCopy = useDeletePageCopy({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListPageCopyQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const summaryItems = fields
    .map((field) => ({
      field,
      value: renderFieldValue(copy, field),
    }))
    .filter((item): item is { field: PageFieldDefinition; value: string } => Boolean(item.value));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-2">
        <CardTitle className="text-base font-semibold">
          {optionLabel(PAGE_KEY_LABELS, copy.page_key, lang)}
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (display) {
                toggleEnabled.mutate({
                  itemId: display.id,
                  data: { is_enabled: !display.is_enabled },
                });
              } else {
                createDisplayOpt.mutate({
                  data: { page_key: copy.page_key, is_enabled: true },
                });
              }
            }}
          >
            {display?.is_enabled !== false ? t("siteConfig.enabled") : t("siteConfig.disabled")}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              if (editing) {
                setForm(buildFormState(copy.page_key, copy));
                setSettingsJson(display ? JSON.stringify(display.settings, null, 2) : "{}");
              }
              setEditing((current) => !current);
            }}
          >
            {editing ? <X className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              if (confirm(t("siteConfig.deletePageConfirm"))) {
                delCopy.mutate({ itemId: copy.id });
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {!editing ? (
          <div className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            {summaryItems.map(({ field, value }) => (
              <div key={field.key}>
                <span className="text-muted-foreground">{field.label}:</span>{" "}
                {value}
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {fields.map((field) => (
                <div
                  key={field.key}
                  className={field.input === "textarea" || field.input === "list" ? "space-y-1 md:col-span-2" : "space-y-1"}
                >
                  <LabelWithHelp
                    label={field.optional ? `${field.label}（可选）` : field.label}
                    title={field.helpTitle}
                    description={field.helpDescription}
                    usageTitle="会影响这些位置"
                    usageItems={field.usageItems}
                  />
                  {renderFieldInput(field, form[field.key] ?? "", (nextValue) =>
                    setForm((current) => ({ ...current, [field.key]: nextValue })),
                  )}
                </div>
              ))}

              <div className="space-y-1 md:col-span-2">
                <Button
                  size="sm"
                  onClick={() =>
                    saveCopy.mutate({
                      itemId: copy.id,
                      data: buildCopyPayload(copy.page_key, form, copy.extras ?? {}),
                    })
                  }
                  disabled={
                    saveCopy.isPending ||
                    !(form.title ?? "").trim() ||
                    !(form.subtitle ?? "").trim()
                  }
                >
                  <Save className="mr-1 h-3 w-3" />
                  {t("siteConfig.saveCopy")}
                </Button>
              </div>
            </div>

            <div className="space-y-3 rounded-2xl border border-border/60 bg-muted/20 p-4">
              <LabelWithHelp
                label="高级显示设置 JSON"
                title="页面开关之外的高级显示选项"
                description="这里保留原始显示设置 JSON，适合维护当前还没有拆成单独表单字段的高级配置。当前常见用途包括列表页搜索开关、简历下载开关等。"
                usageTitle="会影响这些位置"
                usageItems={[
                  "页面显示开关和高级布局选项",
                  "尚未拆成独立字段的显示设置",
                ]}
              />
              <Textarea
                value={settingsJson}
                onChange={(event) => setSettingsJson(event.target.value)}
                rows={12}
                className="font-mono text-xs"
              />
              <Button
                size="sm"
                onClick={() => {
                  try {
                    const parsed = JSON.parse(settingsJson);
                    if (display) {
                      saveSettings.mutate({
                        itemId: display.id,
                        data: { settings: parsed },
                      });
                    } else {
                      createDisplayOpt.mutate({
                        data: { page_key: copy.page_key, settings: parsed },
                      });
                    }
                  } catch {
                    toast.error("显示设置 JSON 格式不正确");
                  }
                }}
                disabled={saveSettings.isPending || createDisplayOpt.isPending}
              >
                <Save className="mr-1 h-3 w-3" />
                {t("siteConfig.saveSettings")}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
