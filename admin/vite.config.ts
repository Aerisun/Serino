import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const normalizeBasePath = (value: string, fallback: string) => {
  const trimmed = value.trim();
  const candidate = trimmed || fallback;
  return candidate.endsWith("/") ? candidate : `${candidate}/`;
};

const appendUnprefixedBackdropFilter = (css: string) =>
  css.replace(/-webkit-backdrop-filter:([^;{}]+)(;?)/g, (match, value, terminator, offset) => {
    const ruleStart = css.lastIndexOf("{", offset);
    const ruleEnd = css.indexOf("}", offset);
    const ruleBody = css.slice(ruleStart + 1, ruleEnd === -1 ? css.length : ruleEnd);

    if (/(^|;)backdrop-filter:/.test(ruleBody)) {
      return match;
    }

    return `${match}${terminator ? "" : ";"}backdrop-filter:${value};`;
  });

const adminBackdropFilterRules = [
  [".admin-glass", "blur(var(--admin-blur-sm)) saturate(var(--admin-saturate))"],
  [".admin-glass-strong", "blur(var(--admin-blur-lg)) saturate(var(--admin-saturate))"],
  [".admin-glass-sidebar", "blur(var(--admin-blur-md)) saturate(var(--admin-saturate))"],
  [".admin-glass-topbar", "blur(var(--admin-blur-sm)) saturate(var(--admin-saturate))"],
  [".admin-glass-input", "blur(4px) saturate(var(--admin-saturate))"],
] as const;

const preserveBackdropFilterPlugin = () => ({
  name: "aerisun-admin-preserve-backdrop-filter",
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

const assertBackdropFilterPlugin = () => ({
  name: "aerisun-admin-backdrop-filter-assertions",
  apply: "build" as const,
  closeBundle() {
    const assetsDir = path.resolve(__dirname, "dist/assets");
    const builtCss = fs.existsSync(assetsDir)
      ? fs
          .readdirSync(assetsDir)
          .filter((fileName) => fileName.endsWith(".css"))
          .map((fileName) => fs.readFileSync(path.join(assetsDir, fileName), "utf-8"))
          .join("\n")
      : "";

    for (const [selector, value] of adminBackdropFilterRules) {
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
    }
  },
});

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const apiBaseUrl = (env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  const backendPort = env.AERISUN_PORT || "8000";
  const adminPort = parseInt(env.AERISUN_ADMIN_PORT || "3001", 10);
  const adminBasePath = normalizeBasePath(env.AERISUN_ADMIN_BASE_PATH || "", "/admin/");
  const apiBasePath = (env.AERISUN_API_BASE_PATH || "/api").replace(/\/+$/, "");

  return {
    base: adminBasePath,
    define: {
      __AERISUN_ADMIN_BASE_PATH__: JSON.stringify(adminBasePath),
      __AERISUN_API_BASE_URL__: JSON.stringify(apiBaseUrl),
      __SERINO_DEV__: JSON.stringify(mode !== "production"),
    },
    server: {
      host: "::",
      port: adminPort,
      allowedHosts: true,
      proxy: {
        [apiBasePath]: {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
        },
        "/media": {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
    plugins: [react(), preserveBackdropFilterPlugin(), assertBackdropFilterPlugin()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
