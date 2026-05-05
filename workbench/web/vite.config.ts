import { defineConfig } from "vite";

const BFF_TARGET = process.env.BFF_TARGET ?? "http://127.0.0.1:3101";

export default defineConfig({
  server: {
    port: 5173,
    host: "0.0.0.0",
    // Vite 5+ rejects requests from hosts not on this list. Without
    // this, the workbench loads blank inside a GitHub Codespace
    // because the forwarded URL (`*.app.github.dev`) is blocked. We
    // also allow `localhost` / `127.0.0.1` for the local-dev path and
    // any custom override via VITE_ALLOWED_HOSTS (comma-separated).
    allowedHosts: [
      "localhost",
      "127.0.0.1",
      ".app.github.dev",
      ...(process.env.VITE_ALLOWED_HOSTS ?? "").split(",").filter(Boolean),
    ],
    proxy: {
      "^/api/.*": {
        target: BFF_TARGET,
        changeOrigin: true,
      },
    },
  },
});
