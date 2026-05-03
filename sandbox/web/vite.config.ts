import { defineConfig } from "vite";

const BFF_TARGET = process.env.BFF_TARGET ?? "http://127.0.0.1:3001";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "^/api/.*": {
        target: BFF_TARGET,
        changeOrigin: true,
      },
    },
  },
});
