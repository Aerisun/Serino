import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetProfileApiV1AdminSiteConfigProfileGet,
  useUpdateProfileApiV1AdminSiteConfigProfilePut,
  useListPoems,
  useCreatePoems,
  useUpdatePoems,
  useDeletePoems,
  getGetProfileApiV1AdminSiteConfigProfileGetQueryKey,
  getListPoemsQueryKey,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { DataTable } from "@/components/DataTable";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type {
  PoemAdminRead,
  SiteProfileAdminRead,
} from "@serino/api-client/models";

const HITOKOTO_TYPE_OPTIONS = [
  { value: "a", labelKey: "siteConfig.poemTypeAnime" },
  { value: "b", labelKey: "siteConfig.poemTypeComic" },
  { value: "c", labelKey: "siteConfig.poemTypeGame" },
  { value: "d", labelKey: "siteConfig.poemTypeLiterature" },
  { value: "e", labelKey: "siteConfig.poemTypeOriginal" },
  { value: "f", labelKey: "siteConfig.poemTypeInternet" },
  { value: "g", labelKey: "siteConfig.poemTypeOther" },
  { value: "h", labelKey: "siteConfig.poemTypeVideo" },
  { value: "i", labelKey: "siteConfig.poemTypePoetry" },
  { value: "j", labelKey: "siteConfig.poemTypeNetease" },
  { value: "k", labelKey: "siteConfig.poemTypePhilosophy" },
  { value: "l", labelKey: "siteConfig.poemTypeJoke" },
] as const;

const DEFAULT_HITOKOTO_TYPES = ["d", "i"];
const POEM_PREVIEW_ENDPOINT = "/api/v1/site/poem-preview";

type PoemSourceMode = "custom" | "hitokoto";

type PoemSettingsForm = {
  poem_source: PoemSourceMode;
  poem_hitokoto_types: string[];
  poem_hitokoto_keywords: string[];
};

type PoemPreviewPayload = {
  mode: PoemSourceMode;
  content: string;
  attribution?: string | null;
};

const createPoemSettingsForm = (
  profile?: SiteProfileAdminRead | null,
): PoemSettingsForm => ({
  poem_source: profile?.poem_source ?? "custom",
  poem_hitokoto_types: [...(profile?.poem_hitokoto_types ?? [])],
  poem_hitokoto_keywords: [...(profile?.poem_hitokoto_keywords ?? [])],
});

const parseKeywords = (value: string) =>
  value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean);

function buildPoemPreviewUrl(
  settings: PoemSettingsForm,
  strict = false,
) {
  const params = new URLSearchParams();
  const activeTypes =
    settings.poem_hitokoto_types.length > 0
      ? settings.poem_hitokoto_types
      : DEFAULT_HITOKOTO_TYPES;

  params.set("mode", settings.poem_source);
  activeTypes.forEach((type) => params.append("types", type));
  settings.poem_hitokoto_keywords.forEach((keyword) =>
    params.append("keywords", keyword),
  );
  if (strict) {
    params.set("strict", "true");
  }
  return `${POEM_PREVIEW_ENDPOINT}?${params.toString()}`;
}

async function fetchPoemPreview(
  settings: PoemSettingsForm,
  strict = false,
) {
  const response = await fetch(buildPoemPreviewUrl(settings, strict), {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Ignore non-JSON error payloads and fall back to HTTP status text.
    }
    throw new Error(message);
  }
  return (await response.json()) as PoemPreviewPayload;
}

export function PoemsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profileRaw } = useGetProfileApiV1AdminSiteConfigProfileGet();
  const { data: raw } = useListPoems();
  const data = raw?.data;
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ content: "", order_index: 0 });
  const [testingPoem, setTestingPoem] = useState("");
  const [isTestingPoem, setIsTestingPoem] = useState(false);
  const [keywordDraft, setKeywordDraft] = useState("");
  const [settingsForm, setSettingsForm] = useState<PoemSettingsForm>(
    createPoemSettingsForm(),
  );
  const [savedSettingsForm, setSavedSettingsForm] =
    useState<PoemSettingsForm | null>(null);
  const rollbackSettingsRef = useRef<PoemSettingsForm | null>(null);
  const submittedSettingsRef = useRef<PoemSettingsForm | null>(null);

  const profileId = profileRaw?.data?.id ?? "";
  const profile = profileRaw?.data as SiteProfileAdminRead | undefined;

  const create = useCreatePoems({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListPoemsQueryKey() });
        setOpen(false);
        resetForm();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg =
          error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const update = useUpdatePoems({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListPoemsQueryKey() });
        setEditingId(null);
        setOpen(false);
        resetForm();
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg =
          error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const del = useDeletePoems({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListPoemsQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const msg =
          error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
    },
  });

  const saveProfile = useUpdateProfileApiV1AdminSiteConfigProfilePut({
    mutation: {
      onSuccess: (response) => {
        const nextProfile = response.data as SiteProfileAdminRead | undefined;
        const nextSettings =
          nextProfile
            ? createPoemSettingsForm(nextProfile)
            : submittedSettingsRef.current ?? settingsForm;
        setSettingsForm(nextSettings);
        setSavedSettingsForm(nextSettings);
        queryClient.invalidateQueries({
          queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
        });
        rollbackSettingsRef.current = null;
        submittedSettingsRef.current = null;
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        const fallback =
          rollbackSettingsRef.current ??
          savedSettingsForm ??
          createPoemSettingsForm(profile);
        setSettingsForm(fallback);
        setKeywordDraft(fallback.poem_hitokoto_keywords.join(", "));
        rollbackSettingsRef.current = null;
        submittedSettingsRef.current = null;
        const msg =
          error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
      },
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

  useEffect(() => {
    if (profile && !savedSettingsForm) {
      const nextSettings = createPoemSettingsForm(profile);
      setSettingsForm(nextSettings);
      setSavedSettingsForm(nextSettings);
    }
  }, [profile, savedSettingsForm]);

  useEffect(() => {
    setKeywordDraft(settingsForm.poem_hitokoto_keywords.join(", "));
  }, [settingsForm.poem_hitokoto_keywords]);

  const poemSource = settingsForm.poem_source;
  const selectedTypes = settingsForm.poem_hitokoto_types;
  const effectiveSelectedTypes =
    selectedTypes.length > 0 ? selectedTypes : DEFAULT_HITOKOTO_TYPES;

  function persistPoemSettings(nextSettings: PoemSettingsForm) {
    rollbackSettingsRef.current = settingsForm;
    submittedSettingsRef.current = nextSettings;
    setSettingsForm(nextSettings);
    saveProfile.mutate({ data: nextSettings });
  }

  function updatePoemSettings(next: Partial<PoemSettingsForm>) {
    persistPoemSettings({
      poem_source: next.poem_source ?? settingsForm.poem_source,
      poem_hitokoto_types:
        next.poem_hitokoto_types ?? settingsForm.poem_hitokoto_types,
      poem_hitokoto_keywords:
        next.poem_hitokoto_keywords ?? settingsForm.poem_hitokoto_keywords,
    });
  }

  function toggleHitokotoType(type: string, checked: boolean) {
    const next = checked
      ? [...new Set([...effectiveSelectedTypes, type])]
      : effectiveSelectedTypes.filter((item) => item !== type);
    if (next.length === 0) {
      toast.error(t("siteConfig.poemHitokotoTypesRequired"));
      return;
    }
    updatePoemSettings({ poem_hitokoto_types: next });
  }

  async function testHitokotoFetch() {
    setIsTestingPoem(true);
    try {
      const payload = await fetchPoemPreview(
        {
          ...settingsForm,
          poem_source: "hitokoto",
        },
        true,
      );
      const content = payload.content?.trim();
      if (!content) {
        throw new Error("empty poem");
      }
      setTestingPoem(
        payload.attribution ? `${content} —— ${payload.attribution}` : content,
      );
      toast.success(t("siteConfig.poemTestSuccess"));
    } catch (error) {
      setTestingPoem("");
      toast.error(
        error instanceof Error && error.message !== "empty poem"
          ? `${t("siteConfig.poemTestFailed")} (${error.message})`
          : t("siteConfig.poemTestFailed"),
      );
    } finally {
      setIsTestingPoem(false);
    }
  }

  return (
    <div className="mt-4 max-w-4xl space-y-8">
      <div className="space-y-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground/70">
          {t("siteConfig.poemSource")}
        </div>
        <div className="max-w-3xl rounded-2xl border border-border/80 bg-background/70 px-4 py-4">
          <div className="mb-4 text-sm font-semibold">
            {t("siteConfig.poemSourceMode")}
          </div>
          <div className="grid gap-3 md:grid-cols-2 md:items-stretch">
            <button
              type="button"
              onClick={() => updatePoemSettings({ poem_source: "custom" })}
              disabled={saveProfile.isPending}
              className={[
                "rounded-2xl border px-4 py-4 text-left transition-colors",
                poemSource === "custom"
                  ? "border-foreground bg-foreground text-background"
                  : "border-border/70 bg-background/60 text-foreground hover:border-foreground/40 hover:bg-background",
              ].join(" ")}
            >
              <div className="text-sm font-semibold">
                {t("siteConfig.poemSourceCustom")}
              </div>
              <div
                className={
                  poemSource === "custom"
                    ? "mt-1 text-xs text-background/80"
                    : "mt-1 text-xs text-muted-foreground"
                }
              >
                {t("siteConfig.poemSourceCustomDesc")}
              </div>
            </button>

            <button
              type="button"
              onClick={() => updatePoemSettings({ poem_source: "hitokoto" })}
              disabled={saveProfile.isPending}
              className={[
                "rounded-2xl border px-4 py-4 text-left transition-colors",
                poemSource === "hitokoto"
                  ? "border-foreground bg-foreground text-background"
                  : "border-border/70 bg-background/60 text-foreground hover:border-foreground/40 hover:bg-background",
              ].join(" ")}
            >
              <div className="text-sm font-semibold">
                {t("siteConfig.poemSourceHitokoto")}
              </div>
              <div
                className={
                  poemSource === "hitokoto"
                    ? "mt-1 text-xs text-background/80"
                    : "mt-1 text-xs text-muted-foreground"
                }
              >
                {t("siteConfig.poemSourceHitokotoDesc")}
              </div>
            </button>
          </div>
        </div>
      </div>

      {poemSource === "hitokoto" ? (
        <div className="space-y-6">
          <div className="space-y-6">
            <div className="space-y-3">
              <div className="text-sm font-semibold">
                {t("siteConfig.poemOnlineConfigTitle")}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {HITOKOTO_TYPE_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className="flex cursor-pointer items-center gap-2 rounded-xl border border-border/80 bg-background px-3 py-2.5 text-sm transition-colors hover:border-foreground/10"
                  >
                    <input
                      type="checkbox"
                      checked={effectiveSelectedTypes.includes(option.value)}
                      onChange={(e) =>
                        toggleHitokotoType(option.value, e.target.checked)
                      }
                      disabled={saveProfile.isPending}
                    />
                    <span>{t(option.labelKey)}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="max-w-2xl space-y-3">
              <div className="text-sm font-semibold">
                {t("siteConfig.poemKeywordPreference")}
              </div>
              <Textarea
                value={keywordDraft}
                onChange={(e) => setKeywordDraft(e.target.value)}
                rows={2}
                placeholder={t("siteConfig.poemKeywordPreferencePlaceholder")}
              />
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="secondary"
                  onClick={() =>
                    updatePoemSettings({
                      poem_hitokoto_keywords: parseKeywords(keywordDraft),
                    })
                  }
                  disabled={saveProfile.isPending}
                >
                  {saveProfile.isPending
                    ? t("common.saving")
                    : t("siteConfig.poemKeywordSave")}
                </Button>
              </div>
            </div>
          </div>

          <div className="max-w-2xl rounded-2xl border border-border/80 bg-background/70 px-5 py-4 shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
              <Button
                onClick={() => void testHitokotoFetch()}
                disabled={isTestingPoem || saveProfile.isPending}
                className="shrink-0 md:h-10 md:self-stretch"
              >
                {isTestingPoem
                  ? t("siteConfig.poemTesting")
                  : t("siteConfig.poemTestAction")}
              </Button>
              <div className="min-h-10 min-w-0 flex-1 rounded-xl border border-dashed border-border px-4 py-2 text-sm text-muted-foreground md:flex md:items-center">
                {testingPoem ? (
                  <div className="text-foreground/85">{testingPoem}</div>
                ) : (
                  <div>{t("siteConfig.poemTestHint")}</div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="text-sm font-semibold">
                {t("siteConfig.poemManualConfigTitle")}
              </div>
              <p className="text-sm text-muted-foreground">
                {t("siteConfig.poemCustomListHint")}
              </p>
            </div>
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
                  <Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addPoem")}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>
                    {editingId
                      ? t("siteConfig.editPoem")
                      : t("siteConfig.newPoem")}
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <Label>{t("siteConfig.content")}</Label>
                    <Textarea
                      value={form.content}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, content: e.target.value }))
                      }
                      rows={4}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>{t("common.order")}</Label>
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
                  <Button
                    onClick={() =>
                      editingId
                        ? update.mutate({ itemId: editingId, data: form })
                        : create.mutate({
                            data: { ...form, site_profile_id: profileId },
                          })
                    }
                    disabled={create.isPending || update.isPending}
                  >
                    {editingId ? t("common.save") : t("common.create")}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="overflow-hidden rounded-2xl border border-border/80 bg-background shadow-[0_8px_30px_rgba(15,23,42,0.04)]">
            <DataTable<PoemAdminRead>
              columns={[
                {
                  header: t("siteConfig.content"),
                  accessor: (row) => (
                    <span className="line-clamp-2">{row.content}</span>
                  ),
                },
                { header: t("common.order"), accessor: "order_index" as any },
                {
                  header: "",
                  accessor: (row) => (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          startEdit(row);
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          del.mutate({ itemId: row.id });
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ),
                },
              ]}
              data={data?.items ?? []}
              total={data?.total ?? 0}
            />
          </div>
        </>
      )}
    </div>
  );
}
