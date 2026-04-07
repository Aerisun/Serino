import { useState, useMemo, useEffect, useRef, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useGetDefaultContentTitle } from "@serino/api-client/admin";
import type { ContentCreate, ContentUpdate, GetDefaultContentTitleContentType } from "@serino/api-client/models";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { useContentPreview } from "@/lib/useContentPreview";
import { extractApiErrorMessage } from "@/lib/api-error";
import {
  buildNextContentSaveForm,
  clearEditorDraftSnapshot,
  hasMeaningfulEditorContent,
  invalidateContentEditorQueries,
  isManualPublishedAtValid,
  moveEditorDraftSnapshot,
  readEditorDraftSnapshot,
  readSavedPublishedAtManualState,
  resolvePublishedAtState,
  saveEditorDraftSnapshot,
  savePublishedAtManualState,
  type ContentEditorSaveMode,
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

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useContentEditor(config: ContentEditorConfig) {
  const { id } = useParams();
  const isNew = id === "new";
  const isDefaultTitleContentType =
    config.contentType === "thoughts" || config.contentType === "excerpts";
  const defaultTitleContentType = (
    isDefaultTitleContentType ? config.contentType : "thoughts"
  ) as GetDefaultContentTitleContentType;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoSaveInFlightRef = useRef(false);
  const pendingAutoSaveRef = useRef(false);
  const currentRouteIdRef = useRef<string | undefined>(id);
  const formRef = useRef<ContentCreate>(config.defaultForm);
  const manualPublishedAtRef = useRef(false);
  const hydratedRef = useRef(false);
  const baselineSnapshotRef = useRef("");
  const forceAutoSaveRef = useRef(false);
  const suggestedTitleRef = useRef("");
  const appliedSuggestedTitleRef = useRef(false);
  const titleEditedRef = useRef(false);

  // ---- Fetch ----
  const { data: itemData } = config.hooks.useGet(id!, {
    query: { enabled: !isNew && !!id },
  });
  const item = itemData?.data;
  const { data: defaultTitleSuggestion } = useGetDefaultContentTitle(
    { content_type: defaultTitleContentType },
    {
      query: {
        enabled: isNew && isDefaultTitleContentType,
        staleTime: 60_000,
        refetchOnWindowFocus: false,
      },
    },
  );

  // ---- Form state ----
  const [form, setForm] = useState<ContentCreate>(config.defaultForm);
  const [isPublishedAtManual, setIsPublishedAtManual] = useState(false);

  const buildDraftSignature = (nextForm: ContentCreate, manualState: boolean) =>
    JSON.stringify({ form: nextForm, isPublishedAtManual: manualState });

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
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    autoSaveInFlightRef.current = false;
    pendingAutoSaveRef.current = false;
    hydratedRef.current = false;
    suggestedTitleRef.current = "";
    appliedSuggestedTitleRef.current = false;
    titleEditedRef.current = false;

    const draftId = id ?? "new";
    const savedDraft = readEditorDraftSnapshot<ContentCreate>(config.contentType, draftId);
    if (savedDraft) {
      const nextForm = {
        ...config.defaultForm,
        ...savedDraft.form,
      };
      setForm(nextForm);
      setIsPublishedAtManual(savedDraft.isPublishedAtManual);
      baselineSnapshotRef.current = "";
      forceAutoSaveRef.current = true;
      hydratedRef.current = true;
      return;
    }

    setForm(config.defaultForm);
    setIsPublishedAtManual(false);
    baselineSnapshotRef.current = buildDraftSignature(config.defaultForm, false);
    forceAutoSaveRef.current = false;
    if (isNew) {
      hydratedRef.current = true;
    }
  }, [config.contentType, config.defaultForm, id, isNew]);

  useEffect(() => {
    if (!item) {
      return;
    }
    const result = config.serverToForm(item);
    const savedManualState = readSavedPublishedAtManualState(config.contentType, item.id);
    const savedDraft = readEditorDraftSnapshot<ContentCreate>(config.contentType, item.id);
    const nextForm = savedDraft?.form ?? result.form;
    const nextManualState = savedDraft?.isPublishedAtManual ?? savedManualState ?? result.isPublishedAtManual;
    setForm(nextForm);
    setIsPublishedAtManual(nextManualState);
    baselineSnapshotRef.current = savedDraft ? "" : buildDraftSignature(nextForm, nextManualState);
    forceAutoSaveRef.current = Boolean(savedDraft);
    hydratedRef.current = true;
  }, [item]);

  useEffect(() => {
    const suggestedTitle = defaultTitleSuggestion?.data?.title;
    if (!suggestedTitle) {
      return;
    }
    suggestedTitleRef.current = suggestedTitle;
    if (
      !isNew ||
      !isDefaultTitleContentType ||
      !hydratedRef.current ||
      appliedSuggestedTitleRef.current ||
      titleEditedRef.current
    ) {
      return;
    }
    if (form.title.trim()) {
      appliedSuggestedTitleRef.current = true;
      return;
    }
    appliedSuggestedTitleRef.current = true;
    setForm((prev) => {
      if (prev.title.trim()) {
        return prev;
      }
      return { ...prev, title: suggestedTitle };
    });
  }, [defaultTitleSuggestion?.data?.title, form.title, isDefaultTitleContentType, isNew]);

  const setField = (key: string, value: any) => {
    if (key === "title") {
      titleEditedRef.current = true;
    }
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
  const isDraftDirty = buildDraftSignature(form, isPublishedAtManual) !== baselineSnapshotRef.current;
  const hasMeaningfulContent = useMemo(() => {
    const nextForm = { ...form };
    if (
      isNew &&
      isDefaultTitleContentType &&
      !titleEditedRef.current &&
      suggestedTitleRef.current &&
      nextForm.title.trim() === suggestedTitleRef.current
    ) {
      nextForm.title = "";
    }
    return hasMeaningfulEditorContent(nextForm as Record<string, unknown>);
  }, [form, isDefaultTitleContentType, isNew]);

  const persistDraftSnapshot = (draftId: string, nextForm: ContentCreate, manualState: boolean) => {
    if (!hasMeaningfulContent) {
      clearEditorDraftSnapshot(config.contentType, draftId);
      return;
    }
    saveEditorDraftSnapshot(config.contentType, draftId, {
      form: nextForm,
      isPublishedAtManual: manualState,
    });
  };

  type PersistOptions = {
    navigateToList?: boolean;
    silent?: boolean;
    showSuccessToast?: boolean;
    replaceRouteOnCreate?: boolean;
    clearDraftOnSuccess?: boolean;
    skipIfEmptyForNew?: boolean;
  };

  const persist = async (mode: ContentEditorSaveMode, options: PersistOptions = {}) => {
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

    const nextForm = buildNextContentSaveForm(currentForm, mode, currentManualState);
    if (!silent) {
      setIsSaving(true);
    }
    try {
      let savedId = draftId;
      if (currentIsNew) {
        const created = await createItem({ data: nextForm });
        const createdId = created?.data?.id;
        if (typeof createdId !== "string" || createdId.length === 0) {
          throw new Error("Missing created item id");
        }
        savePublishedAtManualState(config.contentType, createdId, currentManualState);
        moveEditorDraftSnapshot(config.contentType, "new", createdId);
        savedId = createdId;
        if (replaceRouteOnCreate) {
          navigate(`/${config.contentType}/${createdId}`, { replace: true });
        }
      } else {
        await updateItem({ itemId: draftId, data: nextForm as ContentUpdate });
        savePublishedAtManualState(config.contentType, draftId, currentManualState);
      }
      await invalidateQueries();
      baselineSnapshotRef.current = buildDraftSignature(nextForm, currentManualState);
      forceAutoSaveRef.current = false;
      if (!navigateToList) {
        setForm(nextForm);
      }
      if (clearDraftOnSuccess) {
        clearEditorDraftSnapshot(config.contentType, "new");
        clearEditorDraftSnapshot(config.contentType, savedId);
      }
      if (showSuccessToast) {
        toast.success(t("common.operationSuccess"));
      }
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

  const runAutoSave = async () => {
    if (autoSaveInFlightRef.current) {
      pendingAutoSaveRef.current = true;
      return;
    }
    autoSaveInFlightRef.current = true;
    try {
      await persist("draft", {
        silent: true,
        showSuccessToast: false,
        replaceRouteOnCreate: true,
        skipIfEmptyForNew: true,
      });
    } finally {
      autoSaveInFlightRef.current = false;
      if (pendingAutoSaveRef.current) {
        pendingAutoSaveRef.current = false;
        void runAutoSave();
      }
    }
  };

  const waitForAutoSave = async () => {
    while (autoSaveInFlightRef.current) {
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
  };

  const save = async (mode: ContentEditorSaveMode) => {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    await waitForAutoSave();
    return persist(mode, {
      navigateToList: mode === "confirm",
      showSuccessToast: true,
      clearDraftOnSuccess: true,
    });
  };

  const exitEditor = async () => {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    await waitForAutoSave();
    await persist("draft", {
      navigateToList: true,
      silent: false,
      showSuccessToast: false,
      clearDraftOnSuccess: true,
      skipIfEmptyForNew: true,
    });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await save("confirm");
  };

  useEffect(() => {
    if (!hydratedRef.current) {
      return;
    }
    if (!forceAutoSaveRef.current && !isDraftDirty) {
      clearEditorDraftSnapshot(config.contentType, id ?? "new");
      return;
    }
    persistDraftSnapshot(id ?? "new", form, isPublishedAtManual);
  }, [config.contentType, form, id, isDraftDirty, isPublishedAtManual]);

  useEffect(() => {
    if (
      !hydratedRef.current ||
      (!forceAutoSaveRef.current && !isDraftDirty) ||
      !hasMeaningfulContent
    ) {
      return;
    }
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      autosaveTimerRef.current = null;
      void runAutoSave();
    }, 800);

    return () => {
      if (autosaveTimerRef.current) {
        clearTimeout(autosaveTimerRef.current);
        autosaveTimerRef.current = null;
      }
    };
  }, [form, hasMeaningfulContent, isDraftDirty, isPublishedAtManual]);

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
        status: item.status,
        visibility: item.visibility,
        published_at: effectivePublishedAt,
        ...extraFields(item),
      } as ContentCreate,
      isPublishedAtManual: hasManualPublishedAt,
    };
  };
}
