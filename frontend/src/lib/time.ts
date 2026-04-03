export const BEIJING_TIME_ZONE = "Asia/Shanghai";

type DateLike = string | number | Date;

const BEIJING_PARTS_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: BEIJING_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

function parseDate(value: DateLike | null | undefined): Date | null {
  if (value == null) {
    return null;
  }
  const parsed = value instanceof Date ? value : new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDateInBeijing(
  value: DateLike | null | undefined,
  locale: string,
  options: Intl.DateTimeFormatOptions,
): string {
  const parsed = parseDate(value);
  if (!parsed) {
    return "";
  }

  return new Intl.DateTimeFormat(locale, {
    timeZone: BEIJING_TIME_ZONE,
    ...options,
  }).format(parsed);
}

export function getBeijingDateParts(value: DateLike) {
  const parsed = parseDate(value);
  if (!parsed) {
    return null;
  }

  const parts = BEIJING_PARTS_FORMATTER.formatToParts(parsed);
  const lookup = new Map(parts.map((part) => [part.type, part.value]));
  return {
    year: Number(lookup.get("year") ?? "0"),
    month: Number(lookup.get("month") ?? "0"),
    day: Number(lookup.get("day") ?? "0"),
    hour: Number(lookup.get("hour") ?? "0"),
    minute: Number(lookup.get("minute") ?? "0"),
    second: Number(lookup.get("second") ?? "0"),
  };
}

export function getBeijingDateKey(value: DateLike): string {
  const parts = getBeijingDateParts(value);
  if (!parts) {
    return "";
  }
  return `${String(parts.year).padStart(4, "0")}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

export function getBeijingNowParts() {
  return getBeijingDateParts(Date.now()) ?? {
    year: 0,
    month: 0,
    day: 0,
    hour: 0,
    minute: 0,
    second: 0,
  };
}

export function normalizeDateKey(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  return getBeijingDateKey(value);
}
