import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8080";

export default defineConfig({
  plugins: [tanstackRouter({ target: "react", autoCodeSplitting: true }), react()],
  server: {
    proxy: {
      "/api": { target: apiProxyTarget, changeOrigin: true },
    },
  },
  test: {
    environment: "happy-dom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
