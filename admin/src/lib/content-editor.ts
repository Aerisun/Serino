import type { QueryClient } from "@tanstack/react-query";

export { extractApiErrorMessage as getMutationErrorMessage } from "./api-error";
import { getCurrentBeijingIsoString } from "./time";

export type ContentEditorSaveMode = "draft" | "confirm";
export type EditorContentType = "posts" | "diary" | "thoughts" | "excerpts";

const MANUAL_PUBLISHED_AT_PREF_KEY = "aerisun-admin-published-at-manual-v1";
const EDITOR_DRAFT_STORAGE_PREFIX = "aerisun-admin-editor-draft-v1";
const PUBLIC_CONTENT_REFRESH_KEY = "aerisun:content-updated:v1";

type SaveableContentForm = {
  status?: string | null;
  visibility?: string | null;
  published_at?: string | null;
};

type PersistedEditorDraft<T> = {
  form: T;
  isPublishedAtManual: boolean;
};

export function resolvePublishedAtState(
  publishedAt: string | null | undefined,
  _updatedAt: string | null | undefined,
) {
  const effectivePublishedAt = publishedAt || null;
  // Do not infer manual mode from timestamps. Default to off unless user explicitly saved manual mode.
  const hasManualPublishedAt = false;

  return {
    effectivePublishedAt,
    hasManualPublishedAt,
  };
}

function readManualPrefMap(): Record<string, boolean> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(MANUAL_PUBLISHED_AT_PREF_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    const result: Record<string, boolean> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === "boolean") {
        result[key] = value;
      }
    }
    return result;
  } catch {
    return {};
  }
}

function writeManualPrefMap(value: Record<string, boolean>) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(MANUAL_PUBLISHED_AT_PREF_KEY, JSON.stringify(value));
  } catch {
    // Ignore localStorage errors (private mode / quota).
  }
}

function manualPrefKey(contentType: EditorContentType, itemId: string) {
  return `${contentType}:${itemId}`;
}

export function readSavedPublishedAtManualState(contentType: EditorContentType, itemId: string): boolean | null {
  const map = readManualPrefMap();
  const key = manualPrefKey(contentType, itemId);
  return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : null;
}

export function savePublishedAtManualState(contentType: EditorContentType, itemId: string, value: boolean) {
  const map = readManualPrefMap();
  map[manualPrefKey(contentType, itemId)] = value;
  writeManualPrefMap(map);
}

export function isManualPublishedAtValid(
  isPublishedAtManual: boolean,
  publishedAt: string | null | undefined,
) {
  if (!isPublishedAtManual) {
    return true;
  }
  return Boolean(publishedAt && !Number.isNaN(new Date(publishedAt).getTime()));
}

export function buildNextContentSaveForm<T extends SaveableContentForm>(
  form: T,
  mode: ContentEditorSaveMode,
  isPublishedAtManual: boolean,
) {
  const nextStatus =
    mode === "draft" ? "draft" : form.visibility === "public" ? "published" : "archived";
  const nextPublishedAt =
    mode === "draft"
      ? (form.published_at ?? null)
      : (isPublishedAtManual && form.published_at
          ? form.published_at
          : (form.published_at ?? getCurrentBeijingIsoString()));

  return {
    ...form,
    status: nextStatus,
    published_at: nextPublishedAt,
  };
}

export async function invalidateContentEditorQueries(
  queryClient: QueryClient,
  {
    listQueryKey,
    detailQueryKey,
  }: {
    listQueryKey: readonly unknown[];
    detailQueryKey?: readonly unknown[];
  },
) {
  await queryClient.invalidateQueries({ queryKey: listQueryKey });
  if (detailQueryKey) {
    await queryClient.invalidateQueries({ queryKey: detailQueryKey });
  }
}

export function announcePublicContentChange(contentType: EditorContentType) {
  if (typeof window === "undefined") {
    return;
  }

  const payload = {
    contentType,
    updatedAt: getCurrentBeijingIsoString(),
  };

  try {
    window.localStorage.setItem(PUBLIC_CONTENT_REFRESH_KEY, JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures.
  }

  window.dispatchEvent(new CustomEvent("aerisun:content-updated", { detail: payload }));
}

function editorDraftKey(contentType: EditorContentType, draftId: string) {
  return `${EDITOR_DRAFT_STORAGE_PREFIX}:${contentType}:${draftId}`;
}

export function readEditorDraftSnapshot<T>(
  contentType: EditorContentType,
  draftId: string,
): PersistedEditorDraft<T> | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(editorDraftKey(contentType, draftId));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as PersistedEditorDraft<T> | null;
    if (!parsed || typeof parsed !== "object" || !("form" in parsed)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveEditorDraftSnapshot<T>(
  contentType: EditorContentType,
  draftId: string,
  value: PersistedEditorDraft<T>,
) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(editorDraftKey(contentType, draftId), JSON.stringify(value));
  } catch {
    // Ignore localStorage errors.
  }
}

export function clearEditorDraftSnapshot(contentType: EditorContentType, draftId: string) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(editorDraftKey(contentType, draftId));
  } catch {
    // Ignore localStorage errors.
  }
}

export function moveEditorDraftSnapshot(contentType: EditorContentType, fromDraftId: string, toDraftId: string) {
  if (fromDraftId === toDraftId) {
    return;
  }
  const existing = readEditorDraftSnapshot(contentType, fromDraftId);
  if (!existing) {
    return;
  }
  saveEditorDraftSnapshot(contentType, toDraftId, existing);
  clearEditorDraftSnapshot(contentType, fromDraftId);
}

export function hasMeaningfulEditorContent(value: Record<string, unknown>) {
  for (const [key, entry] of Object.entries(value)) {
    if (["slug", "status", "visibility", "published_at"].includes(key)) {
      continue;
    }
    if (typeof entry === "string" && entry.trim()) {
      return true;
    }
    if (Array.isArray(entry) && entry.length > 0) {
      return true;
    }
  }
  return false;
}
