import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";
import fs from "fs";
import zlib from "zlib";

const stripTrailingSlash = (value: string) => value.trim().replace(/\/+$/, "") || "/api";
const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const buildBasePathPrefixPattern = (value: string) => {
  const normalized = value.trim().replace(/\/+$/, "");
  return new RegExp(`^${escapeRegExp(normalized)}(?:/|$)`);
};
const seoDocumentPattern = /^\/(?:sitemap|rss|feed|feeds)\.xml$/;
const buildObfuscationTargets = [
  "Powered by ",
  "Aerisun /Serino",
  " · ",
  "All Rights Reserved",
  "https://github.com/Aerisun/Serino",
  "Open Aerisun /Serino repository",
  "M7 7h10v10 M7 17 17 7",
] as const;
const FRONTEND_ENTRY_JS_GZIP_BUDGET_BYTES = 60 * 1024;
const FRONTEND_ENTRY_CSS_GZIP_BUDGET_BYTES = 12 * 1024;
const PRECACHE_BUDGET_BYTES = 2 * 1024 * 1024;

const encodeBuildLiteral = (value: string, quote: '"' | "'" | "`") =>
  Array.from(value)
    .map((char) => {
      if (char === "\\") return "\\\\";
      if (char === quote) return `\\${quote}`;
      if (quote === "`" && char === "$") return "\\x24";
      const codePoint = char.codePointAt(0) ?? 0;
      if (codePoint <= 0xff) {
        return `\\x${codePoint.toString(16).padStart(2, "0")}`;
      }
      return `\\u${codePoint.toString(16).padStart(4, "0")}`;
    })
    .join("");

const replaceQuotedLiteral = (code: string, value: string) => {
  let next = code;
  for (const quote of [`"`, `'`, "`"] as const) {
    const escapedValue =
      quote === `"`
        ? JSON.stringify(value).slice(1, -1)
        : quote === `'`
          ? value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")
          : value.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$\{/g, "\\${");
    const pattern = new RegExp(`${escapeRegExp(quote)}${escapeRegExp(escapedValue)}${escapeRegExp(quote)}`, "g");
    next = next.replace(pattern, `${quote}${encodeBuildLiteral(value, quote)}${quote}`);
  }
  return next;
};

const footerBuildObfuscationPlugin = () => ({
  name: "aerisun-footer-build-obfuscation",
  apply: "build" as const,
  enforce: "post" as const,
  generateBundle(_: unknown, bundle: Record<string, { type: string; code?: string }>) {
    for (const output of Object.values(bundle)) {
      if (output.type !== "chunk" || typeof output.code !== "string") continue;
      let nextCode = output.code;
      for (const target of buildObfuscationTargets) {
        nextCode = replaceQuotedLiteral(nextCode, target);
      }
      output.code = nextCode;
    }
  },
});

const performanceBudgetPlugin = () => ({
  name: "aerisun-performance-budgets",
  apply: "build" as const,
  closeBundle() {
    const distDir = path.resolve(__dirname, "dist");
    const indexHtmlPath = path.join(distDir, "index.html");
    if (!fs.existsSync(indexHtmlPath)) {
      return;
    }

    const indexHtml = fs.readFileSync(indexHtmlPath, "utf-8");
    const entryScriptMatch = indexHtml.match(/<script type="module" crossorigin src="([^"]+)"><\/script>/);
    const entryStyleMatch = indexHtml.match(/<link rel="stylesheet" crossorigin href="([^"]+)">/);

    const requiredFileSize = (assetPath: string | undefined, budgetBytes: number, label: string) => {
      if (!assetPath) {
        throw new Error(`Missing ${label} asset in dist/index.html`);
      }
      const relativePath = assetPath.replace(/^\//, "");
      const absolutePath = path.join(distDir, relativePath);
      const gzipBytes = zlib.gzipSync(fs.readFileSync(absolutePath)).length;
      if (gzipBytes > budgetBytes) {
        throw new Error(`${label} gzip budget exceeded: ${gzipBytes} > ${budgetBytes}`);
      }
    };

    requiredFileSize(entryScriptMatch?.[1], FRONTEND_ENTRY_JS_GZIP_BUDGET_BYTES, "entry JS");
    requiredFileSize(entryStyleMatch?.[1], FRONTEND_ENTRY_CSS_GZIP_BUDGET_BYTES, "entry CSS");

    if (/createLucideIcon-[\w-]+\.js/.test(indexHtml)) {
      throw new Error("Homepage should not modulepreload lucide-react startup chunks");
    }

    const swPath = path.join(distDir, "sw.js");
    if (!fs.existsSync(swPath)) {
      return;
    }

    const swContent = fs.readFileSync(swPath, "utf-8");
    const precachedUrls = Array.from(swContent.matchAll(/url:\s*["']([^"']+)["']/g))
      .map((match) => match[1])
      .filter((value) => value.startsWith("/") || !/^https?:\/\//.test(value));
    const totalPrecacheBytes = Array.from(new Set(precachedUrls)).reduce((total, urlValue) => {
      const relativePath = urlValue.replace(/^\//, "");
      const absolutePath = path.join(distDir, relativePath);
      return total + (fs.existsSync(absolutePath) ? fs.statSync(absolutePath).size : 0);
    }, 0);

    if (totalPrecacheBytes > PRECACHE_BUDGET_BYTES) {
      throw new Error(`PWA precache budget exceeded: ${totalPrecacheBytes} > ${PRECACHE_BUDGET_BYTES}`);
    }
  },
});

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const apiBaseUrl = (env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  const apiBasePath = stripTrailingSlash(env.AERISUN_API_BASE_PATH ?? "/api");
  const adminBasePath = (env.AERISUN_ADMIN_BASE_PATH ?? "/admin/").trim() || "/admin/";
  const explicitAdminBaseUrl = (env.VITE_ADMIN_BASE_URL ?? "").replace(/\/+$/, "");
  const adminPort = parseInt(env.AERISUN_ADMIN_PORT || "3001", 10);
  const adminBaseUrl =
    explicitAdminBaseUrl || (mode !== "production" ? `http://127.0.0.1:${adminPort}` : "");
  const walineBasePath = stripTrailingSlash(env.AERISUN_WALINE_BASE_PATH ?? "/waline");
  const apiBasePathPattern = new RegExp(`${escapeRegExp(apiBasePath)}/`);
  const apiBasePathPrefixPattern = buildBasePathPrefixPattern(apiBasePath);
  const adminBasePathPattern = buildBasePathPrefixPattern(adminBasePath);
  const walineBasePathPattern = buildBasePathPrefixPattern(walineBasePath);
  const feedsBasePathPattern = /^\/feeds(?:\/|$)/;
  const walinePort = env.WALINE_PORT || "8360";

  return {
    define: {
      __AERISUN_API_BASE_URL__: JSON.stringify(apiBaseUrl),
      __AERISUN_API_BASE_PATH__: JSON.stringify(apiBasePath),
      __AERISUN_ADMIN_BASE_PATH__: JSON.stringify(adminBasePath),
      __AERISUN_ADMIN_BASE_URL__: JSON.stringify(adminBaseUrl),
      __AERISUN_WALINE_BASE_PATH__: JSON.stringify(walineBasePath),
      __SERINO_DEV__: JSON.stringify(mode !== "production"),
    },
    server: {
      host: "::",
      port: parseInt(env.AERISUN_FRONTEND_PORT || "8080", 10),
      allowedHosts: true,
      hmr: {
        overlay: false,
      },
      proxy: {
        [apiBasePath]: {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/media": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/manifest.webmanifest": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/sitemap.xml": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/feed.xml": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/rss.xml": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/feeds.xml": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        "/feeds": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
          changeOrigin: true,
        },
        [walineBasePath]: {
          target: `http://127.0.0.1:${walinePort}`,
          changeOrigin: true,
        },
      },
    },
    plugins: [
      react(),
      footerBuildObfuscationPlugin(),
      performanceBudgetPlugin(),
      VitePWA({
        registerType: "autoUpdate",
        manifest: false,
        workbox: {
          globPatterns: [
            "assets/index-*.js",
            "assets/index-*.css",
            "fonts/barlow-400-latin.woff2",
          ],
          navigateFallback: null,
          maximumFileSizeToCacheInBytes: 384 * 1024,
          navigateFallbackDenylist: [
            adminBasePathPattern,
            apiBasePathPrefixPattern,
            walineBasePathPattern,
            feedsBasePathPattern,
            seoDocumentPattern,
          ],
          runtimeCaching: [
            {
              urlPattern: /\/assets\/.+\.(js|css|png|jpe?g|svg|gif|webp|avif|woff2?)$/i,
              handler: "CacheFirst",
              options: {
                cacheName: "asset-cache",
                cacheableResponse: { statuses: [0, 200] },
                expiration: { maxEntries: 120, maxAgeSeconds: 86400 * 30 },
              },
            },
          ],
        },
      }),
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
