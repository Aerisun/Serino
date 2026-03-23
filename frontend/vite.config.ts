import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");

  return {
    server: {
      host: "::",
      port: parseInt(env.AERISUN_FRONTEND_PORT || "8080", 10),
      hmr: {
        overlay: false,
      },
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${env.AERISUN_PORT || "8000"}`,
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
              urlPattern: /\/api\//,
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
