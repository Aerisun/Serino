export const PAGE_SIZE_MIN = 1;
export const PAGE_SIZE_MAX = 50;

export function clampPageSize(value: number | null | undefined, fallback: number) {
  const candidate = Number(value ?? fallback);
  if (!Number.isFinite(candidate)) return fallback;
  return Math.min(Math.max(Math.floor(candidate), PAGE_SIZE_MIN), PAGE_SIZE_MAX);
}