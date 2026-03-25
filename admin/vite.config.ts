import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const backendPort = env.AERISUN_PORT || "8000";
  const adminPort = parseInt(env.AERISUN_ADMIN_PORT || "3001", 10);
  const adminBasePath = "/admin/";

  return {
    base: adminBasePath,
    define: {
      __AERISUN_ADMIN_BASE_PATH__: JSON.stringify(adminBasePath),
      __SERINO_DEV__: JSON.stringify(mode !== "production"),
    },
    server: {
      port: adminPort,
      proxy: {
        "/api": {
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
