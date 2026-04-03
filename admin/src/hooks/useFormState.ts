import { useCallback, useState } from "react";

/**
 * Generic form state hook that encapsulates the common pattern of:
 * - Holding a mutable `form` and an immutable `savedSnapshot`
 * - Syncing both when server data arrives
 * - Computing `isDirty` via JSON comparison
 * - Providing `setField` / `reset` helpers
 *
 * Usage:
 *   const { form, setField, isDirty, sync } = useFormState(defaultForm);
 *   useEffect(() => { if (data) sync(toForm(data)); }, [data]);
 */
export function useFormState<T extends Record<string, unknown>>(initialValue: T) {
  const [form, setForm] = useState<T>(initialValue);
  const [savedSnapshot, setSavedSnapshot] = useState<T>(initialValue);

  const isDirty = JSON.stringify(form) !== JSON.stringify(savedSnapshot);

  const setField = useCallback(
    <K extends keyof T>(key: K, value: T[K]) =>
      setForm((prev) => ({ ...prev, [key]: value })),
    [],
  );

  /** Replace both form and savedSnapshot (e.g. after fetching server data). */
  const sync = useCallback((next: T) => {
    setForm(next);
    setSavedSnapshot(next);
  }, []);

  /** Discard edits and revert to the last synced state. */
  const reset = useCallback(() => setForm(savedSnapshot), [savedSnapshot]);

  return { form, setForm, setField, savedSnapshot, isDirty, reset, sync } as const;
}
