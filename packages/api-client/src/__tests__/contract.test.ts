import { describe, it, expect } from "vitest";
import { readdirSync } from "fs";
import { basename } from "path";

// Import generated Zod schemas
import {
  ReadSiteConfigApiV1SiteSiteGetResponse,
  ReadPageCopyApiV1SitePagesGetResponse,
  ReadPostsApiV1SitePostsGetResponse,
  HealthzApiV1SiteHealthzGetResponse,
  MeApiV1AdminAuthMeGetResponse,
  ListPostsResponse,
  ListSessionsEndpointApiV1AdminAuthSessionsGetResponse,
} from "../generated/schemas.zod";
import { FIXTURES_DIR, fixturesDirectoryExists, loadFixture } from "./contract-helpers";

// Map fixture file names to their corresponding Zod schemas
const fixtureSchemaMap: Record<string, { schema: unknown; name: string }> = {
  "public_site_config.json": {
    schema: ReadSiteConfigApiV1SiteSiteGetResponse,
    name: "ReadSiteConfigApiV1SiteSiteGetResponse",
  },
  "public_pages.json": {
    schema: ReadPageCopyApiV1SitePagesGetResponse,
    name: "ReadPageCopyApiV1SitePagesGetResponse",
  },
  "public_posts_list.json": {
    schema: ReadPostsApiV1SitePostsGetResponse,
    name: "ReadPostsApiV1SitePostsGetResponse",
  },
  "public_healthz.json": {
    schema: HealthzApiV1SiteHealthzGetResponse,
    name: "HealthzApiV1SiteHealthzGetResponse",
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

describe("API Contract Validation", () => {
  if (!fixturesDirectoryExists()) {
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
