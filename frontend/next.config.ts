import path from "node:path"
import { fileURLToPath } from "node:url"

import type { NextConfig } from "next"

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000"
const frontendRoot = path.dirname(fileURLToPath(import.meta.url))

const nosniff = { key: "X-Content-Type-Options", value: "nosniff" }
const referrer = { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" }
const widgetReferrer = { key: "Referrer-Policy", value: "no-referrer" }
const toApi = (source: string) => ({ source, destination: `${apiOrigin}${source}` })
const API_REWRITES = [
  "/auth/:path*",
  "/api/public/:path*",
  "/api/conversations",
  "/api/conversations/:path*",
  "/api/canned-replies",
  "/api/canned-replies/:path*",
  "/api/sites",
  "/api/sites/:path*",
  "/api/articles/:path*",
  "/api/kb-sources/:path*",
  "/api/kb-pages/:path*",
  "/api/kb-chunks/:path*",
  "/api/handoffs/:path*",
  "/api/logs",
  "/api/logs/:path*",
  "/api/status",
  "/api/knowledge-gaps",
  "/api/knowledge-gaps/:path*",
  "/api/visitor-blocks",
  "/api/visitor-blocks/:path*",
].map(toApi)
// Staff CSP (nonce + strict-dynamic) is applied per-request in src/proxy.ts.

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: frontendRoot,
  },
  allowedDevOrigins: ["widget.localhost", "host.localhost", "localhost", "127.0.0.1"],
  async headers() {
    return [
      {
        source: "/widget",
        headers: [nosniff, widgetReferrer],
      },
      {
        source: "/admin/:path*",
        headers: [nosniff, referrer],
      },
      {
        source: "/login",
        headers: [nosniff, referrer],
      },
    ]
  },
  async redirects() {
    return [
      { source: "/inbox", destination: "/admin/inbox", permanent: true },
      { source: "/inbox/:path*", destination: "/admin/inbox/:path*", permanent: true },
      { source: "/sites", destination: "/admin/sites", permanent: true },
      { source: "/sites/:path*", destination: "/admin/sites/:path*", permanent: true },
      { source: "/knowledge", destination: "/admin/knowledge", permanent: true },
      { source: "/knowledge/:path*", destination: "/admin/knowledge/:path*", permanent: true },
      { source: "/settings", destination: "/admin/settings", permanent: true },
      { source: "/settings/:path*", destination: "/admin/settings/:path*", permanent: true },
    ]
  },
  async rewrites() {
    return API_REWRITES
  },
}

export default nextConfig
