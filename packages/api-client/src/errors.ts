export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const normalizeErrorMessage = (detail: unknown): string | null => {
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }
        const record = item as { msg?: unknown; loc?: unknown };
        const msg = typeof record.msg === "string" ? record.msg.trim() : "";
        const loc = Array.isArray(record.loc)
          ? record.loc
              .filter(
                (value): value is string | number =>
                  typeof value === "string" || typeof value === "number",
              )
              .join(".")
          : "";
        if (!msg) {
          return null;
        }
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter((item): item is string => Boolean(item));

    return parts.length ? parts.join("; ") : null;
  }

  return null;
};
