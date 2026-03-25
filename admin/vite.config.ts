import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const normalizeBasePath = (value: string, fallback: string) => {
  const trimmed = value.trim();
  const candidate = trimmed || fallback;
  return candidate.endsWith("/") ? candidate : `${candidate}/`;
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const backendPort = env.AERISUN_PORT || "8000";
  const adminPort = parseInt(env.AERISUN_ADMIN_PORT || "3001", 10);
  const adminBasePath = normalizeBasePath(env.AERISUN_ADMIN_BASE_PATH || "", "/admin/");
  const apiBasePath = (env.AERISUN_API_BASE_PATH || "/api").replace(/\/+$/, "");

  return {
    base: adminBasePath,
    define: {
      __AERISUN_ADMIN_BASE_PATH__: JSON.stringify(adminBasePath),
      __SERINO_DEV__: JSON.stringify(mode !== "production"),
    },
    server: {
      port: adminPort,
      proxy: {
        [apiBasePath]: {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});
