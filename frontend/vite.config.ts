import { defineConfig, loadEnv, type Plugin } from "vite";
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
const seoDocumentPattern = /^\/(?:(?:sitemap|rss|feed|feeds)\.xml|(?:robots|llms)\.txt|resume\.md)$/;
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

const appendUnprefixedBackdropFilter = (css: string) =>
  css.replace(/-webkit-backdrop-filter:([^;{}]+);/g, (match, value, offset) => {
    const ruleStart = css.lastIndexOf("{", offset);
    const ruleEnd = css.indexOf("}", offset);
    const ruleBody = css.slice(ruleStart + 1, ruleEnd === -1 ? css.length : ruleEnd);

    if (/(^|;)backdrop-filter:/.test(ruleBody)) {
      return match;
    }

    return `${match}backdrop-filter:${value};`;
  });

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

const preserveBackdropFilterPlugin = () => ({
  name: "aerisun-preserve-backdrop-filter",
  apply: "build" as const,
  enforce: "post" as const,
  generateBundle(_: unknown, bundle: Record<string, { type: string; fileName?: string; source?: string | Uint8Array }>) {
    for (const output of Object.values(bundle)) {
      if (output.type !== "asset" || typeof output.source !== "string" || !output.fileName?.endsWith(".css")) {
        continue;
      }
      output.source = appendUnprefixedBackdropFilter(output.source);
    }
  },
});

const copyRequestHeaders = (headers: Record<string, string | string[] | undefined>) => {
  const next = new Headers();
  for (const [key, value] of Object.entries(headers)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        next.append(key, item);
      }
      continue;
    }
    if (value !== undefined) {
      next.set(key, value);
    }
  }
  return next;
};

const seoHtmlDevProxyBlockedResponseHeaders = new Set([
  "content-security-policy",
  "content-length",
]);

const crawlerUserAgentPattern =
  /(bot|crawler|spider|crawling|slurp|bingpreview|facebookexternalhit|twitterbot|linkedinbot|discordbot|telegrambot|whatsapp|googlebot|googleother|google-inspectiontool|google-agent|google-notebooklm|google-read-aloud|bingbot|baiduspider|bytespider|doubaobot|oai-searchbot|chatgpt-user|perplexitybot|claude-searchbot|claude-user|curl|wget|python-requests|httpx)/i;
const crawlerOnlySeoHtmlPathPattern = /^\/(?:posts(?:\/[^/?#]+)?|diary(?:\/[^/?#]+)?|thoughts|excerpts|friends|guestbook)$/;

const isAlwaysSeoHtmlPath = (pathname: string) => pathname === "/" || pathname === "/resume";

const isCrawlerOnlySeoHtmlPath = (pathname: string) => crawlerOnlySeoHtmlPathPattern.test(pathname);

const isCrawlerRequest = (headers: Record<string, string | string[] | undefined>) => {
  const userAgent = headers["user-agent"];
  const normalizedUserAgent = Array.isArray(userAgent) ? userAgent.join(" ") : (userAgent ?? "");
  return crawlerUserAgentPattern.test(normalizedUserAgent);
};

const seoHtmlDevProxyPlugin = (target: string): Plugin => ({
  name: "aerisun-seo-html-dev-proxy",
  configureServer(server) {
    server.middlewares.use(async (req, res, next) => {
      if (req.method !== "GET" && req.method !== "HEAD") {
        next();
        return;
      }
      if (!req.url) {
        next();
        return;
      }

      const url = new URL(req.url, target);
      const shouldProxySeoHtml =
        isAlwaysSeoHtmlPath(url.pathname) ||
        (isCrawlerOnlySeoHtmlPath(url.pathname) && isCrawlerRequest(req.headers));
      if (!shouldProxySeoHtml) {
        next();
        return;
      }

      try {
        const upstreamUrl = new URL(`${url.pathname}${url.search}`, target);
        const headers = copyRequestHeaders(req.headers);
        headers.set("host", upstreamUrl.host);
        const upstream = await fetch(upstreamUrl, {
          method: req.method,
          headers,
          redirect: "manual",
        });

        res.statusCode = upstream.status;
        if (req.method === "HEAD") {
          upstream.headers.forEach((value, key) => {
            if (!seoHtmlDevProxyBlockedResponseHeaders.has(key.toLowerCase())) {
              res.setHeader(key, value);
            }
          });
          res.end();
          return;
        }

        upstream.headers.forEach((value, key) => {
          if (!seoHtmlDevProxyBlockedResponseHeaders.has(key.toLowerCase())) {
            res.setHeader(key, value);
          }
        });
        const html = await upstream.text();
        const transformedHtml = await server.transformIndexHtml(url.pathname, html);
        res.end(transformedHtml);
      } catch (error) {
        next(error as Error);
      }
    });
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

    const assetsDir = path.join(distDir, "assets");
    const builtCss = fs.existsSync(assetsDir)
      ? fs
          .readdirSync(assetsDir)
          .filter((fileName) => fileName.endsWith(".css"))
          .map((fileName) => fs.readFileSync(path.join(assetsDir, fileName), "utf-8"))
          .join("\n")
      : "";
    const assertBackdropFilterPair = (selector: string, value: string) => {
      const normalizedValue = value.replace(/\s+/g, "");
      const ruleBodies = Array.from(builtCss.matchAll(new RegExp(`${escapeRegExp(selector)}\\{([^}]*)\\}`, "g"))).map(
        (match) => match[1].replace(/\s+/g, ""),
      );
      const standardPattern = new RegExp(`(?:^|;)backdrop-filter:${escapeRegExp(normalizedValue)};`);
      const prefixedPattern = new RegExp(`(?:^|;)-webkit-backdrop-filter:${escapeRegExp(normalizedValue)};`);
      const hasPair = ruleBodies.some((body) => standardPattern.test(body) && prefixedPattern.test(body));

      if (!hasPair) {
        throw new Error(`${selector} must keep both backdrop-filter declarations in built CSS`);
      }
    };

    assertBackdropFilterPair(".liquid-glass-nav-hero", "blur(24px) saturate(146%)");
    assertBackdropFilterPair(".liquid-glass-nav-hero-strong", "blur(28px) saturate(152%)");

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
  const apiBasePathPrefixPattern = buildBasePathPrefixPattern(apiBasePath);
  const adminBasePathPattern = buildBasePathPrefixPattern(adminBasePath);
  const walineBasePathPattern = buildBasePathPrefixPattern(walineBasePath);
  const feedsBasePathPattern = /^\/feeds(?:\/|$)/;
  const walinePort = env.WALINE_PORT || "8360";
  const apiProxyTarget = `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`;

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
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/media": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/manifest.webmanifest": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/sitemap.xml": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/robots.txt": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/llms.txt": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/resume.md": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/feed.xml": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/rss.xml": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/feeds.xml": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        "/feeds": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        [walineBasePath]: {
          target: `http://127.0.0.1:${walinePort}`,
          changeOrigin: true,
        },
      },
    },
    plugins: [
      seoHtmlDevProxyPlugin(apiProxyTarget),
      react(),
      footerBuildObfuscationPlugin(),
      preserveBackdropFilterPlugin(),
      performanceBudgetPlugin(),
      VitePWA({
        // Retire previously shipped service workers that could keep serving stale
        // HTML/CSS after Docker upgrades. New pages should not register it again.
        selfDestroying: true,
        injectRegister: false,
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
