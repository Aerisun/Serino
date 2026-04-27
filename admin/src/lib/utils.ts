export { cn } from "@serino/utils/cn";
import { formatDateInBeijing } from "./time";

export function formatDate(date: string | Date | null | undefined): string {
  if (date == null) return "-";
  return formatDateInBeijing(date);
}

export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}
