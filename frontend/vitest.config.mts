import path from "node:path"
import { fileURLToPath } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

const root = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.join(root, "src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "embed-loader/**/*.test.ts"],
    env: {
      NEXT_PUBLIC_WIDGET_ORIGIN: "http://widget.localhost:3000",
      NEXT_PUBLIC_STAFF_APP_ORIGIN: "http://localhost:3000",
      NEXT_PUBLIC_DEMO_SITE_KEY: "demo",
      NEXT_PUBLIC_DEMO_PUBLIC_KEY:
        "969b9f156001b582403251fcc58e281102ae6c2549c7ec09db917b6a0f493b0a",
      NEXT_PUBLIC_API_ORIGIN: "http://127.0.0.1:8000",
    },
  },
})
