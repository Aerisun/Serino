import { existsSync, readFileSync } from "fs";
import { resolve } from "path";

export const FIXTURES_DIR = resolve(__dirname, "fixtures");

const NAIVE_DATETIME_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;

export function normalizeDatetimes(value: unknown): unknown {
  if (typeof value === "string" && NAIVE_DATETIME_RE.test(value)) {
    return `${value}Z`;
  }
  if (Array.isArray(value)) {
    return value.map(normalizeDatetimes);
  }
  if (value !== null && typeof value === "object") {
    const obj: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
      obj[key] = normalizeDatetimes(entry);
    }
    return obj;
  }
  return value;
}

export function loadFixture(filename: string): unknown {
  const filepath = resolve(FIXTURES_DIR, filename);
  const raw = JSON.parse(readFileSync(filepath, "utf-8"));
  return normalizeDatetimes(raw);
}

export function fixturesDirectoryExists() {
  return existsSync(FIXTURES_DIR);
}
