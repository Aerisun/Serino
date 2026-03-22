import { useEffect, useRef, useCallback } from "react";

interface UseAutoSaveOptions {
  key: string;
  data: any;
  enabled?: boolean;
  debounceMs?: number;
}

export function useAutoSave({ key, data, enabled = true, debounceMs = 30000 }: UseAutoSaveOptions) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const dataRef = useRef(data);
  dataRef.current = data;

  const saveDraft = useCallback(() => {
    try {
      localStorage.setItem(`draft:${key}`, JSON.stringify(dataRef.current));
    } catch {
      // localStorage quota exceeded — ignore
    }
  }, [key]);

  const loadDraft = useCallback((): any | null => {
    try {
      const stored = localStorage.getItem(`draft:${key}`);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  }, [key]);

  const clearDraft = useCallback(() => {
    localStorage.removeItem(`draft:${key}`);
  }, [key]);

  const hasDraft = useCallback((): boolean => {
    return localStorage.getItem(`draft:${key}`) !== null;
  }, [key]);

  // Auto-save on data change
  useEffect(() => {
    if (!enabled) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(saveDraft, debounceMs);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [data, enabled, debounceMs, saveDraft]);

  // Save on unmount
  useEffect(() => {
    return () => {
      if (enabled) saveDraft();
    };
  }, [enabled, saveDraft]);

  return { saveDraft, loadDraft, clearDraft, hasDraft };
}
