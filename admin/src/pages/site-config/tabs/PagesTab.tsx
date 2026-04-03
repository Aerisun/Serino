import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListPageCopy,
  useCreatePageCopy,
  useUpdatePageCopy,
  useDeletePageCopy,
  getListPageCopyQueryKey,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import { DirtySaveButton } from "@/components/ui/DirtySaveButton";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { ArrowLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";
import { PAGE_KEYS, PAGE_KEY_LABELS, optionLabel } from "../constants";
import type { PageCopyAdminRead } from "@serino/api-client/models";
import {
  getAdvancedFieldsForPage,
  getPrimaryFieldsForPage,
  type PageFieldDefinition,
  WIDTH_OPTIONS,
} from "../page-field-defs";

type PageFormState = Record<string, string> & { page_key: string };

const emptyCreateForm = (): PageFormState => ({ page_key: "" });

const PAGE_SIZE_MIN = 1;
const PAGE_SIZE_MAX = 30;

const PAGE_FORM_DEFAULTS: Record<string, Partial<Record<string, string>>> = {
  posts: { page_size: "15" },
  diary: { page_size: "15" },
  excerpts: { page_size: "15" },
  thoughts: { page_size: "15" },
  friends: { page_size: "10" },
};

const getDefaultFieldValue = (pageKey: string, fieldKey: string) => PAGE_FORM_DEFAULTS[pageKey]?.[fieldKey] ?? "";

const getPageSizeError = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed)) {
    return "请输入 1 到 30 的整数";
  }
  if (parsed < PAGE_SIZE_MIN || parsed > PAGE_SIZE_MAX) {
    return "每次加载条数必须在 1 到 30 之间";
  }
  return "";
};

const getFormErrors = (form: PageFormState) => {
  const errors: Record<string, string> = {};
  const pageSizeValue = form.page_size;
  if (typeof pageSizeValue === "string" && pageSizeValue.trim()) {
    const pageSizeError = getPageSizeError(pageSizeValue);
    if (pageSizeError) {
      errors.page_size = pageSizeError;
    }
  }
  return errors;
};

const readFieldValue = (
  pageKey: string,
  copy: Pick<PageCopyAdminRead, "extras"> & Record<string, unknown>,
  field: PageFieldDefinition,
) => {
  if (field.source === "base") {
    const raw = copy[field.key];
    return raw == null ? getDefaultFieldValue(pageKey, field.key) : String(raw);
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
  for (const field of [...getPrimaryFieldsForPage(pageKey), ...getAdvancedFieldsForPage(pageKey)]) {
    state[field.key] = copy
      ? readFieldValue(pageKey, copy as PageCopyAdminRead & Record<string, unknown>, field)
      : getDefaultFieldValue(pageKey, field.key);
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

  for (const field of [...getPrimaryFieldsForPage(pageKey), ...getAdvancedFieldsForPage(pageKey)]) {
    if (field.source === "extra") {
      assignExtraValue(extras, field, form[field.key] ?? "");
    }
  }

  return {
    ...(includePageKey ? { page_key: pageKey } : {}),
    title: (form.title ?? "").trim(),
    subtitle: (form.subtitle ?? "").trim(),
    search_placeholder: normalizeOptionalText(form.search_placeholder ?? ""),
    empty_message: normalizeOptionalText(form.empty_message ?? ""),
    max_width: normalizeOptionalText(form.max_width ?? ""),
    page_size: parseOptionalNumber(form.page_size ?? ""),
    extras,
  };
};

const stableSerialize = (value: unknown): string => {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entryValue]) => `${JSON.stringify(key)}:${stableSerialize(entryValue)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
};

const renderFieldValue = (copy: PageCopyAdminRead, field: PageFieldDefinition) => {
  if (field.source === "base") {
    const raw = copy[field.key as keyof PageCopyAdminRead];
    const defaultValue = getDefaultFieldValue(copy.page_key, field.key);
    const resolved = raw == null || raw === "" ? defaultValue : String(raw);
    if (!resolved) {
      return null;
    }
    if (field.key === "max_width") {
      const match = WIDTH_OPTIONS.find((option) => option.value === resolved);
      return match?.label ?? resolved;
    }
    return resolved;
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
  errorMessage?: string,
) => {
  if (field.input === "textarea" || field.input === "list") {
    return (
      <Textarea
        value={value}
        rows={field.input === "list" ? 4 : 3}
        placeholder={field.placeholder}
        aria-invalid={Boolean(errorMessage)}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  if (field.input === "select") {
    return (
      <select
        className={`flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm ${
          errorMessage ? "border-red-500 focus:border-red-500" : "border-input"
        }`}
        value={value}
        aria-invalid={Boolean(errorMessage)}
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
      min={field.key === "page_size" ? PAGE_SIZE_MIN : undefined}
      max={field.key === "page_size" ? PAGE_SIZE_MAX : undefined}
      step={field.input === "number" ? 1 : undefined}
      aria-invalid={Boolean(errorMessage)}
      className={errorMessage ? "border-red-500 focus-visible:ring-red-500" : undefined}
      onChange={(event) => onChange(event.target.value)}
    />
  );
};

export function PagesTab() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const { data: copyRaw } = useListPageCopy();
  const copies = useMemo(() => copyRaw?.data?.items ?? [], [copyRaw]);
  const orderedCopies = useMemo(
    () =>
      [...copies].sort(
        (left, right) => PAGE_KEYS.indexOf(left.page_key) - PAGE_KEYS.indexOf(right.page_key),
      ),
    [copies],
  );

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<PageFormState>(emptyCreateForm());
  const createPrimaryFields = createForm.page_key ? getPrimaryFieldsForPage(createForm.page_key) : [];
  const createAdvancedFields = createForm.page_key ? getAdvancedFieldsForPage(createForm.page_key) : [];
  const createFormErrors = useMemo(
    () => (createForm.page_key ? getFormErrors({ ...createForm }) : {}),
    [createForm],
  );
  const createHasValidationErrors = Object.values(createFormErrors).some(Boolean);

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

              {createPrimaryFields.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {createPrimaryFields.map((field) => (
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
                      {renderFieldInput(field, createForm[field.key] ?? "", (nextValue) =>
                        setCreateForm((current) => ({ ...current, [field.key]: nextValue })), createFormErrors[field.key])}
                      {createFormErrors[field.key] ? (
                        <p className="text-sm text-destructive">{createFormErrors[field.key]}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}

              {createAdvancedFields.length > 0 ? (
                <CollapsibleSection
                  title="高级配置"
                  badge={`${createAdvancedFields.length}`}
                >
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {createAdvancedFields.map((field) => (
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
                        {renderFieldInput(field, createForm[field.key] ?? "", (nextValue) =>
                          setCreateForm((current) => ({ ...current, [field.key]: nextValue })), createFormErrors[field.key])}
                        {createFormErrors[field.key] ? (
                          <p className="text-sm text-destructive">{createFormErrors[field.key]}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </CollapsibleSection>
              ) : null}

              <Button
                onClick={() =>
                  createCopy.mutate({
                    data: buildCopyPayload(createForm.page_key, createForm, undefined, true),
                  })}
                disabled={
                  createCopy.isPending ||
                  !createForm.page_key ||
                  !(createForm.title ?? "").trim() ||
                  createHasValidationErrors
                }
              >
                {t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {orderedCopies.length === 0 ? (
        <p className="py-4 text-muted-foreground">{t("siteConfig.noPages")}</p>
      ) : null}

      {orderedCopies.map((copy) => (
        <PageRow key={copy.id} copy={copy} />
      ))}
    </div>
  );
}

function PageRow({ copy }: { copy: PageCopyAdminRead }) {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<PageFormState>(() => buildFormState(copy.page_key, copy));
  const primaryFields = getPrimaryFieldsForPage(copy.page_key);
  const advancedFields = getAdvancedFieldsForPage(copy.page_key);
  const formErrors = useMemo(() => getFormErrors({ ...form }), [form]);
  const hasValidationErrors = Object.values(formErrors).some(Boolean);
  const savedPayload = useMemo(
    () => buildCopyPayload(copy.page_key, buildFormState(copy.page_key, copy), copy.extras ?? {}),
    [copy],
  );
  const currentPayload = useMemo(
    () => buildCopyPayload(copy.page_key, form, copy.extras ?? {}),
    [copy.extras, copy.page_key, form],
  );
  const hasChanges = stableSerialize(currentPayload) !== stableSerialize(savedPayload);

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

  const summaryItems = primaryFields
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
          {editing ? (
            <DirtySaveButton
              dirty={hasChanges}
              saving={saveCopy.isPending}
              size="sm"
              className="h-8 px-3"
              disabled={!(form.title ?? "").trim() || hasValidationErrors}
              idleLabel="保存"
              savingLabel={t("common.saving")}
              onClick={() =>
                saveCopy.mutate({
                  itemId: copy.id,
                  data: currentPayload,
                })}
            />
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              if (editing) {
                setForm(buildFormState(copy.page_key, copy));
              }
              setEditing((current) => !current);
            }}
          >
            {editing ? <ArrowLeft className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
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
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {primaryFields.map((field) => (
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
                  setForm((current) => ({ ...current, [field.key]: nextValue })), formErrors[field.key])}
                {formErrors[field.key] ? (
                  <p className="text-sm text-destructive">{formErrors[field.key]}</p>
                ) : null}
              </div>
            ))}

            {advancedFields.length > 0 ? (
              <div className="md:col-span-2">
                <CollapsibleSection
                  title="高级配置"
                  badge={`${advancedFields.length}`}
                >
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {advancedFields.map((field) => (
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
                          setForm((current) => ({ ...current, [field.key]: nextValue })), formErrors[field.key])}
                        {formErrors[field.key] ? (
                          <p className="text-sm text-destructive">{formErrors[field.key]}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </CollapsibleSection>
              </div>
            ) : null}

          </div>
        )}
      </CardContent>
    </Card>
  );
}
