import path from "node:path"
import { fileURLToPath } from "node:url"

import type { NextConfig } from "next"

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000"
const frontendRoot = path.dirname(fileURLToPath(import.meta.url))

const nosniff = { key: "X-Content-Type-Options", value: "nosniff" }
const referrer = { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" }
const widgetReferrer = { key: "Referrer-Policy", value: "no-referrer" }
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
    return [
      {
        source: "/auth/:path*",
        destination: `${apiOrigin}/auth/:path*`,
      },
      {
        source: "/api/public/:path*",
        destination: `${apiOrigin}/api/public/:path*`,
      },
      {
        source: "/api/conversations",
        destination: `${apiOrigin}/api/conversations`,
      },
      {
        source: "/api/conversations/:path*",
        destination: `${apiOrigin}/api/conversations/:path*`,
      },
      {
        source: "/api/canned-replies",
        destination: `${apiOrigin}/api/canned-replies`,
      },
      {
        source: "/api/canned-replies/:path*",
        destination: `${apiOrigin}/api/canned-replies/:path*`,
      },
      {
        source: "/api/sites",
        destination: `${apiOrigin}/api/sites`,
      },
      {
        source: "/api/sites/:path*",
        destination: `${apiOrigin}/api/sites/:path*`,
      },
      {
        source: "/api/articles/:path*",
        destination: `${apiOrigin}/api/articles/:path*`,
      },
      {
        source: "/api/kb-sources/:path*",
        destination: `${apiOrigin}/api/kb-sources/:path*`,
      },
      {
        source: "/api/kb-pages/:path*",
        destination: `${apiOrigin}/api/kb-pages/:path*`,
      },
      {
        source: "/api/kb-chunks/:path*",
        destination: `${apiOrigin}/api/kb-chunks/:path*`,
      },
      {
        source: "/api/handoffs/:path*",
        destination: `${apiOrigin}/api/handoffs/:path*`,
      },
      {
        source: "/api/logs",
        destination: `${apiOrigin}/api/logs`,
      },
      {
        source: "/api/logs/:path*",
        destination: `${apiOrigin}/api/logs/:path*`,
      },
      {
        source: "/api/visitor-blocks",
        destination: `${apiOrigin}/api/visitor-blocks`,
      },
      {
        source: "/api/visitor-blocks/:path*",
        destination: `${apiOrigin}/api/visitor-blocks/:path*`,
      },
    ]
  },
}

export default nextConfig
