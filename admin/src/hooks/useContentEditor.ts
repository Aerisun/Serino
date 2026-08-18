import { useState, useMemo, useEffect, useRef, useCallback, type FormEvent, type SetStateAction } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { getDefaultContentTitle, useGetDefaultContentTitle } from "@serino/api-client/admin";
import type {
  ContentCreate,
  ContentUpdate,
  GetDefaultContentTitleContentType,
  GetDefaultContentTitleParams,
} from "@serino/api-client/models";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { useContentPreview } from "@/lib/useContentPreview";
import { extractApiErrorMessage } from "@/lib/api-error";
import {
  announcePublicContentChange,
  applySynchronizedStateUpdate,
  buildNextContentSaveForm,
  clearEditorDraftSnapshot,
  hasMeaningfulEditorContent,
  invalidateContentEditorQueries,
  isManualPublishedAtValid,
  readEditorDraftSnapshot,
  readSavedPublishedAtManualState,
  readSavedTitleAutoState,
  resolvePublishedAtState,
  saveEditorDraftSnapshot,
  savePublishedAtManualState,
  saveTitleAutoState,
} from "@/lib/content-editor";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ContentType = "posts" | "diary" | "thoughts" | "excerpts";

export interface ContentEditorHooks {
  useGet: (id: string, opts: { query: { enabled: boolean } }) => { data?: { data?: any } };
  useCreate: (opts: any) => { mutateAsync: (arg: { data: any }) => Promise<any> };
  useUpdate: (opts: any) => { mutateAsync: (arg: { itemId: string; data: any }) => Promise<any> };
  useDelete: (opts: any) => { mutate: (arg: { itemId: string }) => void };
  getListQueryKey: () => readonly unknown[];
  getDetailQueryKey: (id: string) => readonly unknown[];
}

export interface ContentEditorConfig {
  contentType: ContentType;
  hooks: ContentEditorHooks;
  /** Route to navigate to after deletion (e.g. "/posts"). */
  listRoute: string;
  /** Default empty form for new content. */
  defaultForm: ContentCreate;
  /** Maps a server item to the ContentCreate form shape. */
  serverToForm: (item: any) => { form: ContentCreate; isPublishedAtManual: boolean };
  /** i18n keys */
  i18nKeys: {
    newTitle: string;
    editTitle: string;
    deleteConfirm: string;
  };
  /** Optional: custom preview path builder. Defaults to `/{type}/{slug}?preview...` */
  buildPreviewPath?: (slug: string, storageKey: string) => string;
}

const AUTO_TITLE_PATTERNS: Partial<Record<ContentType, RegExp>> = {
  diary: /^\d{1,2}年\d{1,2}月\d{1,2}日记$/,
  thoughts: /^碎碎念[零一二三四五六七八九十百\d]+则 \(\d{1,2}\.\d{1,2}\.\d{1,2}\.\)$/,
  excerpts: /^文摘[零一二三四五六七八九十百\d]+则 \(\d{1,2}\.\d{1,2}\.\d{1,2}\.\)$/,
};

function normalizeAutoTitleCategory(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized || undefined;
}

function buildAutoTitleValue(
  contentType: ContentType,
  suggestion: { title: string },
) {
  return contentType === "diary" || contentType === "thoughts" || contentType === "excerpts"
    ? suggestion.title
    : "";
}

function isLikelyAutoTitle(contentType: ContentType, title: string | null | undefined) {
  if (!title) {
    return false;
  }
  const pattern = AUTO_TITLE_PATTERNS[contentType];
  return pattern ? pattern.test(title.trim()) : false;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useContentEditor(config: ContentEditorConfig) {
  const { id } = useParams();
  const isNew = id === "new";
  const isDefaultTitleContentType =
    config.contentType === "diary" ||
    config.contentType === "thoughts" ||
    config.contentType === "excerpts";
  const defaultTitleContentType = (
    isDefaultTitleContentType ? config.contentType : "thoughts"
  ) as GetDefaultContentTitleContentType;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const currentRouteIdRef = useRef<string | undefined>(id);
  const formRef = useRef<ContentCreate>(config.defaultForm);
  const manualPublishedAtRef = useRef(false);
  const autoTitleEnabledRef = useRef(isDefaultTitleContentType && isNew);
  const hydratedRef = useRef(false);
  const baselineSnapshotRef = useRef("");
  const sourceUpdatedAtRef = useRef<string | null>(null);
  const suggestedTitleRef = useRef("");
  const defaultTitleParamsKeyRef = useRef("");

  // ---- Fetch ----
  const { data: itemData } = config.hooks.useGet(id!, {
    query: { enabled: !isNew && !!id },
  });
  const item = itemData?.data;
  const [form, setFormState] = useState<ContentCreate>(config.defaultForm);
  const [isPublishedAtManual, setIsPublishedAtManualState] = useState(false);
  const [isAutoTitleEnabled, setIsAutoTitleEnabledState] = useState(isDefaultTitleContentType && isNew);
  const defaultTitleParams = useMemo<GetDefaultContentTitleParams>(() => ({
    content_type: defaultTitleContentType,
    category:
      defaultTitleContentType === "excerpts"
        ? normalizeAutoTitleCategory(form.category)
        : undefined,
    item_id: !isNew && id ? id : undefined,
  }), [defaultTitleContentType, form.category, id, isNew]);
  const defaultTitleParamsKey = JSON.stringify(defaultTitleParams);
  const { data: defaultTitleSuggestion } = useGetDefaultContentTitle(
    defaultTitleParams,
    {
      query: {
        enabled: isDefaultTitleContentType && (isNew || Boolean(item)),
        staleTime: 60_000,
        refetchOnWindowFocus: false,
      },
    },
  );

  const setForm = (value: SetStateAction<ContentCreate>) => {
    setFormState(applySynchronizedStateUpdate(formRef, value));
  };

  const setIsPublishedAtManual = (value: SetStateAction<boolean>) => {
    setIsPublishedAtManualState(applySynchronizedStateUpdate(manualPublishedAtRef, value));
  };

  const setIsAutoTitleEnabled = (value: SetStateAction<boolean>) => {
    setIsAutoTitleEnabledState(applySynchronizedStateUpdate(autoTitleEnabledRef, value));
  };

  const buildDraftSignature = (
    nextForm: ContentCreate,
    manualState: boolean,
    autoTitleEnabled: boolean,
  ) => JSON.stringify({
    form: nextForm,
    isPublishedAtManual: manualState,
    isAutoTitleEnabled: autoTitleEnabled,
  });

  useEffect(() => {
    currentRouteIdRef.current = id;
  }, [id]);

  useEffect(() => {
    formRef.current = form;
  }, [form]);

  useEffect(() => {
    manualPublishedAtRef.current = isPublishedAtManual;
  }, [isPublishedAtManual]);

  useEffect(() => {
    autoTitleEnabledRef.current = isAutoTitleEnabled;
  }, [isAutoTitleEnabled]);

  useEffect(() => {
    hydratedRef.current = false;
    suggestedTitleRef.current = "";
    defaultTitleParamsKeyRef.current = "";
    sourceUpdatedAtRef.current = null;

    const draftId = id ?? "new";
    const snapshot = isNew
      ? readEditorDraftSnapshot(config.contentType, draftId, null)
      : null;
    const nextForm = snapshot
      ? { ...config.defaultForm, ...snapshot.form } as ContentCreate
      : config.defaultForm;
    const nextManualState = snapshot?.isPublishedAtManual ?? false;
    const nextAutoTitleEnabled = snapshot?.isAutoTitleEnabled ?? (isDefaultTitleContentType && isNew);

    setForm(nextForm);
    setIsPublishedAtManual(nextManualState);
    setIsAutoTitleEnabled(nextAutoTitleEnabled);
    baselineSnapshotRef.current = buildDraftSignature(
      config.defaultForm,
      false,
      isDefaultTitleContentType && isNew,
    );
    if (isNew) {
      hydratedRef.current = true;
    }
  }, [config.contentType, config.defaultForm, id, isDefaultTitleContentType, isNew]);

  useEffect(() => {
    if (!item) {
      return;
    }
    const result = config.serverToForm(item);
    const savedManualState = readSavedPublishedAtManualState(config.contentType, item.id);
    const savedAutoTitleState = readSavedTitleAutoState(config.contentType, item.id);
    const sourceUpdatedAt = typeof item.updated_at === "string" ? item.updated_at : null;
    sourceUpdatedAtRef.current = sourceUpdatedAt;
    const snapshot = readEditorDraftSnapshot(config.contentType, item.id, sourceUpdatedAt);
    if (!snapshot) {
      clearEditorDraftSnapshot(config.contentType, item.id);
    }
    const serverManualState = savedManualState ?? result.isPublishedAtManual;
    const serverAutoTitleEnabled = isDefaultTitleContentType
      ? (savedAutoTitleState ?? isLikelyAutoTitle(config.contentType, result.form.title))
      : false;
    const nextForm = snapshot
      ? { ...result.form, ...snapshot.form } as ContentCreate
      : result.form;
    const nextManualState = snapshot?.isPublishedAtManual ?? serverManualState;
    const nextAutoTitleEnabled = snapshot?.isAutoTitleEnabled ?? serverAutoTitleEnabled;
    setForm(nextForm);
    setIsPublishedAtManual(nextManualState);
    setIsAutoTitleEnabled(nextAutoTitleEnabled);
    baselineSnapshotRef.current = buildDraftSignature(
      result.form,
      serverManualState,
      serverAutoTitleEnabled,
    );
    hydratedRef.current = true;
  }, [config.contentType, config.serverToForm, isDefaultTitleContentType, item]);

  useEffect(() => {
    const suggestion = defaultTitleSuggestion?.data;
    if (!suggestion) {
      return;
    }
    const suggestedTitle = buildAutoTitleValue(config.contentType, suggestion);
    suggestedTitleRef.current = suggestedTitle;
    defaultTitleParamsKeyRef.current = defaultTitleParamsKey;
    if (!isDefaultTitleContentType || !hydratedRef.current || !isAutoTitleEnabled) {
      return;
    }
    setForm((prev) => {
      if (prev.title === suggestedTitle) {
        return prev;
      }
      return { ...prev, title: suggestedTitle };
    });
  }, [
    config.contentType,
    defaultTitleParamsKey,
    defaultTitleSuggestion?.data,
    isAutoTitleEnabled,
    isDefaultTitleContentType,
  ]);

  const setField = (key: string, value: any) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  // ---- Query invalidation ----
  const invalidateQueries = async () =>
    invalidateContentEditorQueries(queryClient, {
      listQueryKey: config.hooks.getListQueryKey(),
      detailQueryKey: id && !isNew ? config.hooks.getDetailQueryKey(id) : undefined,
    });

  // ---- Mutations ----
  const { mutateAsync: createItem } = config.hooks.useCreate({});
  const { mutateAsync: updateItem } = config.hooks.useUpdate({});

  const { mutate: deleteItem } = config.hooks.useDelete({
    mutation: {
      onSuccess: () => {
        announcePublicContentChange(config.contentType);
        void invalidateQueries();
        toast.success(t("common.operationSuccess"));
        navigate(config.listRoute);
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  // ---- Save ----
  const [isSaving, setIsSaving] = useState(false);
  const isPublishedAtValid = isManualPublishedAtValid(isPublishedAtManual, form.published_at);
  const isDraftDirty =
    buildDraftSignature(form, isPublishedAtManual, isAutoTitleEnabled) !== baselineSnapshotRef.current;
  const hasMeaningfulContent = useMemo(() => {
    const nextForm = { ...form };
    if (
      isNew &&
      isDefaultTitleContentType &&
      isAutoTitleEnabled &&
      suggestedTitleRef.current &&
      nextForm.title.trim() === suggestedTitleRef.current
    ) {
      nextForm.title = "";
    }
    return hasMeaningfulEditorContent(nextForm as Record<string, unknown>);
  }, [form, isAutoTitleEnabled, isDefaultTitleContentType, isNew]);
  const hasUnsavedChanges = isDraftDirty && (!isNew || hasMeaningfulContent);

  const persistEditorDraftSnapshot = useCallback(() => {
    if (!hydratedRef.current) {
      return;
    }
    const currentForm = formRef.current;
    const currentManualState = manualPublishedAtRef.current;
    const currentAutoTitleEnabled = autoTitleEnabledRef.current;
    const draftId = currentRouteIdRef.current ?? "new";
    const currentIsNew = draftId === "new";
    const isDirty =
      buildDraftSignature(currentForm, currentManualState, currentAutoTitleEnabled) !==
      baselineSnapshotRef.current;
    const formForMeaningfulContent = { ...currentForm };
    if (
      currentIsNew &&
      isDefaultTitleContentType &&
      currentAutoTitleEnabled &&
      suggestedTitleRef.current &&
      formForMeaningfulContent.title?.trim() === suggestedTitleRef.current
    ) {
      formForMeaningfulContent.title = "";
    }
    if (!isDirty || (currentIsNew && !hasMeaningfulEditorContent(formForMeaningfulContent))) {
      return;
    }
    saveEditorDraftSnapshot({
      contentType: config.contentType,
      draftId,
      form: { ...currentForm } as Record<string, unknown>,
      isPublishedAtManual: currentManualState,
      isAutoTitleEnabled: currentAutoTitleEnabled,
      sourceUpdatedAt: sourceUpdatedAtRef.current,
    });
  }, [config.contentType, isDefaultTitleContentType]);

  useEffect(() => {
    if (!hasUnsavedChanges) {
      return;
    }
    const timeoutId = window.setTimeout(persistEditorDraftSnapshot, 800);
    return () => window.clearTimeout(timeoutId);
  }, [form, hasUnsavedChanges, isAutoTitleEnabled, isPublishedAtManual, persistEditorDraftSnapshot]);

  useEffect(() => {
    window.addEventListener("pagehide", persistEditorDraftSnapshot);
    return () => window.removeEventListener("pagehide", persistEditorDraftSnapshot);
  }, [persistEditorDraftSnapshot]);

  type PersistOptions = {
    navigateToList?: boolean;
    silent?: boolean;
    showSuccessToast?: boolean;
    replaceRouteOnCreate?: boolean;
    clearDraftOnSuccess?: boolean;
    skipIfEmptyForNew?: boolean;
  };

  const buildDefaultTitleRequestParams = (
    currentForm: ContentCreate,
    itemId?: string,
  ): GetDefaultContentTitleParams => ({
    content_type: defaultTitleContentType,
    category:
      defaultTitleContentType === "excerpts"
        ? normalizeAutoTitleCategory(currentForm.category)
        : undefined,
    item_id: itemId,
  });

  const resolveAutoTitleForSave = async (
    currentForm: ContentCreate,
    nextForm: ContentCreate,
    draftId: string,
    currentIsNew: boolean,
  ) => {
    if (!isDefaultTitleContentType || !autoTitleEnabledRef.current) {
      return nextForm.title;
    }

    const params = buildDefaultTitleRequestParams(
      currentForm,
      currentIsNew ? undefined : draftId,
    );
    const paramsKey = JSON.stringify(params);
    const currentSuggestion = defaultTitleSuggestion?.data;

    if (currentSuggestion && defaultTitleParamsKeyRef.current === paramsKey) {
      return buildAutoTitleValue(config.contentType, currentSuggestion);
    }

    const response = await getDefaultContentTitle(params);
    const fetchedSuggestion = response.data;
    defaultTitleParamsKeyRef.current = paramsKey;
    return buildAutoTitleValue(config.contentType, fetchedSuggestion);
  };

  const persist = async (options: PersistOptions = {}) => {
    const {
      navigateToList = false,
      silent = false,
      showSuccessToast = !silent,
      replaceRouteOnCreate = false,
      clearDraftOnSuccess = false,
      skipIfEmptyForNew = false,
    } = options;
    const currentForm = formRef.current;
    const currentManualState = manualPublishedAtRef.current;
    const currentAutoTitleEnabled = autoTitleEnabledRef.current;
    const draftId = currentRouteIdRef.current ?? "new";
    const currentIsNew = draftId === "new";

    if (currentManualState && !isManualPublishedAtValid(currentManualState, currentForm.published_at)) {
      if (!silent) {
        toast.error(t("common.invalidDateFormat"));
      }
      return { saved: false as const };
    }

    if (skipIfEmptyForNew && currentIsNew && !hasMeaningfulContent) {
      clearEditorDraftSnapshot(config.contentType, "new");
      if (navigateToList) {
        navigate(config.listRoute);
      }
      return { saved: false as const };
    }

    if (!silent) {
      setIsSaving(true);
    }
    try {
      const nextForm = buildNextContentSaveForm(currentForm, currentManualState);
      if (currentAutoTitleEnabled) {
        nextForm.title = await resolveAutoTitleForSave(
          currentForm,
          nextForm,
          draftId,
          currentIsNew,
        );
      }
      let savedId = draftId;
      if (currentIsNew) {
        const created = await createItem({ data: nextForm });
        const createdId = created?.data?.id;
        if (typeof createdId !== "string" || createdId.length === 0) {
          throw new Error("Missing created item id");
        }
        savePublishedAtManualState(config.contentType, createdId, currentManualState);
        saveTitleAutoState(config.contentType, createdId, currentAutoTitleEnabled);
        savedId = createdId;
        if (replaceRouteOnCreate) {
          navigate(`/${config.contentType}/${createdId}`, { replace: true });
        }
      } else {
        await updateItem({ itemId: draftId, data: nextForm as ContentUpdate });
        savePublishedAtManualState(config.contentType, draftId, currentManualState);
        saveTitleAutoState(config.contentType, draftId, currentAutoTitleEnabled);
      }
      await invalidateQueries();
      baselineSnapshotRef.current = buildDraftSignature(
        nextForm,
        currentManualState,
        currentAutoTitleEnabled,
      );
      setForm(nextForm);
      if (clearDraftOnSuccess) {
        clearEditorDraftSnapshot(config.contentType, "new");
        clearEditorDraftSnapshot(config.contentType, savedId);
      }
      if (showSuccessToast) {
        toast.success(t("common.operationSuccess"));
      }
      announcePublicContentChange(config.contentType);
      if (navigateToList) {
        navigate(config.listRoute);
      }
      return { saved: true as const, savedId, form: nextForm };
    } catch (error) {
      if (!silent) {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      }
      return { saved: false as const };
    } finally {
      if (!silent) {
        setIsSaving(false);
      }
    }
  };

  const save = async () => {
    return persist({
      navigateToList: true,
      showSuccessToast: true,
      clearDraftOnSuccess: true,
    });
  };

  const exitEditor = () => {
    if (hasUnsavedChanges && !window.confirm(t("common.discardChangesConfirm"))) {
      return;
    }
    navigate(config.listRoute);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await save();
  };

  // ---- Preview ----
  const storageKey = `aerisun-preview-${config.contentType}-${id ?? "new"}`;
  const previewPayload = useMemo(
    () => ({ type: config.contentType, ...form }),
    [form, config.contentType],
  );
  const previewPath = useMemo(() => {
    if (config.buildPreviewPath) {
      return config.buildPreviewPath(form.slug, storageKey);
    }
    if (form.slug) {
      return `/${config.contentType}/${encodeURIComponent(form.slug)}?previewStorageKey=${encodeURIComponent(storageKey)}`;
    }
    return `/preview?storageKey=${encodeURIComponent(storageKey)}`;
  }, [form.slug, storageKey, config]);
  const { openPreview } = useContentPreview({
    storageKey,
    payload: previewPayload,
    previewPath,
  });

  // ---- Delete ----
  const confirmDelete = () => {
    if (confirm(t(config.i18nKeys.deleteConfirm))) {
      deleteItem({ itemId: id! });
    }
  };

  // ---- Page title ----
  const pageTitle = isNew ? t(config.i18nKeys.newTitle) : t(config.i18nKeys.editTitle);

  return {
    id,
    isNew,
    form,
    setForm,
    setField,
    isSaving,
    isPublishedAtManual,
    setIsPublishedAtManual,
    isAutoTitleEnabled,
    setIsAutoTitleEnabled,
    isPublishedAtValid,
    save,
    exitEditor,
    handleSubmit,
    confirmDelete,
    openPreview,
    pageTitle,
    t,
  };
}

// ---------------------------------------------------------------------------
// Helper to build serverToForm from common content fields
// ---------------------------------------------------------------------------

export function buildServerToForm(
  extraFields: (item: any) => Record<string, any>,
) {
  return (item: any) => {
    const { effectivePublishedAt, hasManualPublishedAt } = resolvePublishedAtState(
      item.published_at,
      item.updated_at,
    );
    return {
      form: {
        slug: item.slug,
        title: item.title,
        summary: item.summary || "",
        body: item.body,
        tags: item.tags,
        visibility: item.visibility,
        published_at: effectivePublishedAt,
        category: item.category || "",
        ...extraFields(item),
      } as ContentCreate,
      isPublishedAtManual: hasManualPublishedAt,
    };
  };
}
