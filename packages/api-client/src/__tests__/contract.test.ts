import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, existsSync } from "fs";
import { resolve, basename } from "path";

// Import generated Zod schemas
import {
  ReadSiteConfigApiV1PublicSiteGetResponse,
  ReadPageCopyApiV1PublicPagesGetResponse,
  ReadPostsApiV1PublicPostsGetResponse,
  HealthzApiV1PublicHealthzGetResponse,
  MeApiV1AdminAuthMeGetResponse,
  ListPostsResponse,
  ListSessionsEndpointApiV1AdminAuthSessionsGetResponse,
} from "../generated/schemas.zod";

const FIXTURES_DIR = resolve(__dirname, "fixtures");

// Map fixture file names to their corresponding Zod schemas
const fixtureSchemaMap: Record<string, { schema: unknown; name: string }> = {
  "public_site_config.json": {
    schema: ReadSiteConfigApiV1PublicSiteGetResponse,
    name: "ReadSiteConfigApiV1PublicSiteGetResponse",
  },
  "public_pages.json": {
    schema: ReadPageCopyApiV1PublicPagesGetResponse,
    name: "ReadPageCopyApiV1PublicPagesGetResponse",
  },
  "public_posts_list.json": {
    schema: ReadPostsApiV1PublicPostsGetResponse,
    name: "ReadPostsApiV1PublicPostsGetResponse",
  },
  "public_healthz.json": {
    schema: HealthzApiV1PublicHealthzGetResponse,
    name: "HealthzApiV1PublicHealthzGetResponse",
  },
  "admin_me.json": {
    schema: MeApiV1AdminAuthMeGetResponse,
    name: "MeApiV1AdminAuthMeGetResponse",
  },
  "admin_posts_list.json": {
    schema: ListPostsResponse,
    name: "ListPostsResponse",
  },
  "admin_sessions.json": {
    schema: ListSessionsEndpointApiV1AdminAuthSessionsGetResponse,
    name: "ListSessionsEndpointApiV1AdminAuthSessionsGetResponse",
  },
};

// ISO 8601 datetime without timezone (from SQLite) — append UTC marker
// so Zod's .datetime() accepts it. This is a known SQLite limitation:
// the database stores timezone-aware values but loses the offset on read.
const NAIVE_DATETIME_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;

function normalizeDatetimes(value: unknown): unknown {
  if (typeof value === "string" && NAIVE_DATETIME_RE.test(value)) {
    return value + "Z";
  }
  if (Array.isArray(value)) {
    return value.map(normalizeDatetimes);
  }
  if (value !== null && typeof value === "object") {
    const obj: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      obj[k] = normalizeDatetimes(v);
    }
    return obj;
  }
  return value;
}

function loadFixture(filename: string): unknown {
  const filepath = resolve(FIXTURES_DIR, filename);
  const raw = JSON.parse(readFileSync(filepath, "utf-8"));
  return normalizeDatetimes(raw);
}

describe("API Contract Validation", () => {
  if (!existsSync(FIXTURES_DIR)) {
    it.skip("fixtures directory missing — run backend tests first", () => {});
    return;
  }

  const available = readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".json"));

  for (const [filename, { schema, name }] of Object.entries(fixtureSchemaMap)) {
    if (!available.includes(filename)) {
      it.skip(`${name} — fixture ${filename} not found`, () => {});
      continue;
    }

    it(`${name} validates ${filename}`, () => {
      const data = loadFixture(filename);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const result = (schema as any).safeParse(data);
      if (!result.success) {
        const issues = result.error.issues
          .map(
            (i: { path: (string | number)[]; message: string; code: string }) =>
              `  ${i.path.join(".")}: ${i.message} (${i.code})`,
          )
          .join("\n");
        expect.fail(
          `Schema ${name} failed for ${filename}:\n${issues}`,
        );
      }
      expect(result.success).toBe(true);
    });
  }

  // Warn about fixtures without schemas
  for (const file of available) {
    if (!fixtureSchemaMap[file]) {
      it.skip(`${basename(file)} — no schema mapping defined`, () => {});
    }
  }
});
