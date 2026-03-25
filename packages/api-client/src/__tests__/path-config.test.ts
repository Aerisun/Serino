import { afterEach, describe, expect, it, vi } from "vitest";

import adminViteConfig from "../../../../admin/vite.config.ts";
import frontendViteConfig from "../../../../frontend/vite.config.ts";

const setEnv = (entries: Record<string, string | undefined>) => {
  const previous = new Map<string, string | undefined>();
  for (const [key, value] of Object.entries(entries)) {
    previous.set(key, process.env[key]);
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
  return () => {
    for (const [key, value] of previous.entries()) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  };
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("path config", () => {
  it("wires admin base path and api proxy from shared env", () => {
    const restoreEnv = setEnv({
      AERISUN_ADMIN_BASE_PATH: "/control/",
      AERISUN_API_BASE_PATH: "/service/",
      AERISUN_PORT: "8123",
      AERISUN_ADMIN_PORT: "3210",
    });

    try {
      const config = adminViteConfig({ mode: "development" });
      expect(config.base).toBe("/control/");
      expect(config.define?.__AERISUN_ADMIN_BASE_PATH__).toBe(JSON.stringify("/control/"));
      expect(config.server?.proxy?.["/service"]).toMatchObject({
        target: "http://localhost:8123",
        changeOrigin: true,
      });
    } finally {
      restoreEnv();
    }
  });

  it("wires frontend api and waline same-origin paths from shared env", () => {
    const restoreEnv = setEnv({
      AERISUN_API_BASE_PATH: "/service/",
      AERISUN_WALINE_BASE_PATH: "/comment/",
      AERISUN_PORT: "8123",
      AERISUN_FRONTEND_PORT: "4321",
    });

    try {
      const config = frontendViteConfig({ mode: "development" });
      expect(config.define?.__AERISUN_API_BASE_PATH__).toBe(JSON.stringify("/service"));
      expect(config.define?.__AERISUN_WALINE_BASE_PATH__).toBe(JSON.stringify("/comment"));
      expect(config.server?.proxy?.["/service"]).toMatchObject({
        target: "http://127.0.0.1:8123",
        changeOrigin: true,
      });
      expect(config.server?.proxy?.["/comment"]).toMatchObject({
        target: "http://127.0.0.1:8360",
        changeOrigin: true,
      });
    } finally {
      restoreEnv();
    }
  });

  it("exposes the frontend api base path fallback to runtime helpers", async () => {
    const restoreEnv = setEnv({
      AERISUN_API_BASE_PATH: "/service/",
      AERISUN_WALINE_BASE_PATH: "/comment/",
    });
    vi.stubGlobal("__AERISUN_API_BASE_PATH__", "/service/");
    vi.stubGlobal("__AERISUN_WALINE_BASE_PATH__", "/comment/");

    try {
      const apiModule = await import("../../../../frontend/src/lib/api/index.ts");
      expect(apiModule.API_BASE_PATH).toBe("/service");

      vi.doMock("@serino/api-client/public", () => ({
        readCommunityConfigApiV1PublicCommunityConfigGet: vi.fn(async () => {
          throw new Error("offline");
        }),
      }));

      const communityModule = await import("../../../../frontend/src/lib/community-config.ts");
      vi.stubGlobal("window", { location: { origin: "http://localhost:4321" } });

      try {
        const config = await communityModule.loadCommunityConfig();
        expect(config.serverURL).toBe("http://localhost:4321/comment");
      } finally {
        vi.unstubAllGlobals();
      }
    } finally {
      restoreEnv();
    }
  });
});
