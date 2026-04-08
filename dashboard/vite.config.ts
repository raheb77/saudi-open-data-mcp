/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxyTarget = env.DASHBOARD_PROXY_TARGET;
  const bearerToken = env.DASHBOARD_PROXY_BEARER_TOKEN;

  function withOptionalAuthHeader(proxy: any) {
    if (!bearerToken) {
      return;
    }
    proxy.on("proxyReq", (proxyReq: any) => {
      proxyReq.setHeader("Authorization", `Bearer ${bearerToken}`);
    });
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: "127.0.0.1",
      fs: {
        allow: [".."],
      },
      proxy: proxyTarget
        ? {
            "/mcp": {
              target: proxyTarget,
              changeOrigin: true,
              secure: false,
              configure: withOptionalAuthHeader,
            },
            "/readyz": {
              target: proxyTarget,
              changeOrigin: true,
              secure: false,
              configure: withOptionalAuthHeader,
            },
          }
        : undefined,
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  };
});
