import { useEffect, useState } from "react";
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
const HITOKOTO_RETRY_COUNT = 8;

type HitokotoPayload = {
  hitokoto?: string;
  from?: string;
  from_who?: string | null;
};

const normalizeKeywords = (keywords: string[]) =>
  keywords.map((item) => item.trim().toLowerCase()).filter(Boolean);

const parseKeywords = (value: string) =>
  value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean);

const matchesKeywords = (payload: HitokotoPayload, keywords: string[]) => {
  if (keywords.length === 0) return true;
  const haystack = [payload.hitokoto, payload.from, payload.from_who]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword));
};

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
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetProfileApiV1AdminSiteConfigProfileGetQueryKey(),
        });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
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

  const poemSource = profile?.poem_source ?? "custom";
  const selectedTypes = profile?.poem_hitokoto_types ?? [];
  const selectedKeywords = profile?.poem_hitokoto_keywords ?? [];

  useEffect(() => {
    setKeywordDraft(selectedKeywords.join(", "));
  }, [selectedKeywords]);

  function updatePoemSettings(next: {
    poem_source?: "custom" | "hitokoto";
    poem_hitokoto_types?: string[];
    poem_hitokoto_keywords?: string[];
  }) {
    saveProfile.mutate({
      data: {
        poem_source: next.poem_source ?? poemSource,
        poem_hitokoto_types: next.poem_hitokoto_types ?? selectedTypes,
        poem_hitokoto_keywords: next.poem_hitokoto_keywords ?? selectedKeywords,
      },
    });
  }

  function toggleHitokotoType(type: string, checked: boolean) {
    const next = checked
      ? [...new Set([...selectedTypes, type])]
      : selectedTypes.filter((item) => item !== type);
    if (next.length === 0) {
      toast.error(t("siteConfig.poemHitokotoTypesRequired"));
      return;
    }
    updatePoemSettings({ poem_hitokoto_types: next });
  }

  async function fetchHitokotoPreview(types: string[], keywords: string[]) {
    const query = types
      .map((type) => `c=${encodeURIComponent(type)}`)
      .join("&");
    const normalizedKeywords = normalizeKeywords(keywords);
    let lastPayload: HitokotoPayload | null = null;

    for (let attempt = 0; attempt < HITOKOTO_RETRY_COUNT; attempt += 1) {
      const response = await fetch(`https://v1.hitokoto.cn/?${query}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = (await response.json()) as HitokotoPayload;
      lastPayload = payload;
      const content = payload.hitokoto?.trim();
      if (!content) continue;
      if (matchesKeywords(payload, normalizedKeywords)) {
        return payload;
      }
    }

    if (!lastPayload?.hitokoto?.trim()) {
      throw new Error("empty poem");
    }
    return lastPayload;
  }

  async function testHitokotoFetch() {
    const activeTypes =
      selectedTypes.length > 0 ? selectedTypes : DEFAULT_HITOKOTO_TYPES;
    const activeKeywords = selectedKeywords;

    setIsTestingPoem(true);
    try {
      const payload = await fetchHitokotoPreview(activeTypes, activeKeywords);
      const content = payload.hitokoto?.trim();
      if (!content) {
        throw new Error("empty poem");
      }
      const source = [payload.from_who, payload.from]
        .filter(Boolean)
        .join(" · ");
      setTestingPoem(source ? `${content} —— ${source}` : content);
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
                      checked={(selectedTypes.length > 0
                        ? selectedTypes
                        : DEFAULT_HITOKOTO_TYPES
                      ).includes(option.value)}
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
