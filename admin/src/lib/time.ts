const BEIJING_TIME_ZONE = "Asia/Shanghai";

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

function getBeijingDateParts(value: DateLike | null | undefined) {
  const parsed = parseDate(value);
  if (!parsed) {
    return null;
  }

  const parts = BEIJING_PARTS_FORMATTER.formatToParts(parsed);
  const lookup = new Map(parts.map((part) => [part.type, part.value]));
  return {
    year: lookup.get("year") ?? "",
    month: lookup.get("month") ?? "",
    day: lookup.get("day") ?? "",
    hour: lookup.get("hour") ?? "",
    minute: lookup.get("minute") ?? "",
    second: lookup.get("second") ?? "",
  };
}

export function formatDateInBeijing(
  value: DateLike | null | undefined,
  locale = "zh-CN",
  options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  },
) {
  const parsed = parseDate(value);
  if (!parsed) {
    return "-";
  }

  return new Intl.DateTimeFormat(locale, {
    timeZone: BEIJING_TIME_ZONE,
    ...options,
  }).format(parsed);
}

export function formatDateTimeInBeijing(
  value: DateLike | null | undefined,
  locale = "zh-CN",
  options?: Intl.DateTimeFormatOptions,
) {
  return formatDateInBeijing(value, locale, options);
}

export function isoToDatetimeLocalInBeijing(value: string | null | undefined): string {
  const parts = getBeijingDateParts(value ?? null);
  if (!parts) {
    return "";
  }
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function datetimeLocalInBeijingToIso(value: string): string {
  const matched = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
  if (!matched) {
    return "";
  }

  const [, yearRaw, monthRaw, dayRaw, hourRaw, minuteRaw] = matched;
  const shiftedDate = new Date(`${yearRaw}-${monthRaw}-${dayRaw}T${hourRaw}:${minuteRaw}:00+08:00`);
  if (Number.isNaN(shiftedDate.getTime())) {
    return "";
  }
  const normalized = getBeijingDateParts(shiftedDate);
  if (
    !normalized ||
    normalized.year !== yearRaw ||
    normalized.month !== monthRaw ||
    normalized.day !== dayRaw ||
    normalized.hour !== hourRaw ||
    normalized.minute !== minuteRaw
  ) {
    return "";
  }
  return `${yearRaw}-${monthRaw}-${dayRaw}T${hourRaw}:${minuteRaw}:00+08:00`;
}

export function isValidBeijingDatetimeLocal(value: string): boolean {
  if (!value) {
    return true;
  }
  return Boolean(datetimeLocalInBeijingToIso(value));
}

export function getCurrentBeijingIsoString(): string {
  const parts = getBeijingDateParts(Date.now());
  if (!parts) {
    return "";
  }
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}+08:00`;
}
