import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

const stripTrailingSlash = (value: string) => value.trim().replace(/\/+$/, "") || "/api";
const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const apiBaseUrl = (env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  const apiBasePath = stripTrailingSlash(env.AERISUN_API_BASE_PATH ?? "/api");
  const walineBasePath = stripTrailingSlash(env.AERISUN_WALINE_BASE_PATH ?? "/waline");
  const apiBasePathPattern = new RegExp(`${escapeRegExp(apiBasePath)}/`);
  const walinePort = env.WALINE_PORT || "8360";

  return {
    define: {
      __AERISUN_API_BASE_URL__: JSON.stringify(apiBaseUrl),
      __AERISUN_API_BASE_PATH__: JSON.stringify(apiBasePath),
      __AERISUN_WALINE_BASE_PATH__: JSON.stringify(walineBasePath),
      __SERINO_DEV__: JSON.stringify(mode !== "production"),
    },
    server: {
      host: "::",
      port: parseInt(env.AERISUN_FRONTEND_PORT || "8080", 10),
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
        [walineBasePath]: {
          target: `http://127.0.0.1:${walinePort}`,
          changeOrigin: true,
        },
      },
    },
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        manifest: {
          name: "Aerisun",
          short_name: "Aerisun",
          description: "个人博客与创意空间",
          theme_color: "#ffffff",
          background_color: "#ffffff",
          display: "standalone",
          start_url: "/",
          icons: [
            { src: "/favicon.svg", sizes: "any", type: "image/svg+xml" },
          ],
        },
        workbox: {
          runtimeCaching: [
            {
              urlPattern: apiBasePathPattern,
              handler: "NetworkFirst",
              options: { cacheName: "api-cache", expiration: { maxEntries: 50, maxAgeSeconds: 300 } },
            },
            {
              urlPattern: /\.(js|css|png|jpg|jpeg|svg|gif|woff2?)$/,
              handler: "CacheFirst",
              options: { cacheName: "asset-cache", expiration: { maxEntries: 100, maxAgeSeconds: 86400 * 30 } },
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
