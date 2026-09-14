import type { NextConfig } from "next"

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000"
const wsOrigin = apiOrigin.replace(/^http/, "ws")

const frameAncestors = () => {
  const raw =
    process.env.WIDGET_FRAME_ANCESTORS ??
    process.env.APPROVED_FRAME_ANCESTORS ??
    "http://localhost:3000"
  const allowed = raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0 && !part.includes("*"))
  return allowed.join(" ") || "http://localhost:3000"
}

const nosniff = { key: "X-Content-Type-Options", value: "nosniff" }
const referrer = { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" }
// HSTS is enforced at the edge in production.
// Next App Router boots with inline scripts; a static CSP without script-src
// (falling back to default-src 'self') blocks hydration and the login form
// degrades to a native GET that puts credentials in the query string.
// Prefer nonce middleware later; until then allow Next's inline/eval bootstrap.
const staffCsp = {
  key: "Content-Security-Policy",
  value: [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "font-src 'self'",
    `connect-src 'self' ${apiOrigin} ${wsOrigin}`,
    "frame-ancestors 'none'",
  ].join("; "),
}

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["widget.localhost", "host.localhost", "localhost", "127.0.0.1"],
  async headers() {
    return [
      {
        source: "/widget",
        headers: [
          {
            key: "Content-Security-Policy",
            value: `frame-ancestors ${frameAncestors()}`,
          },
          nosniff,
        ],
      },
      {
        source: "/admin/:path*",
        headers: [staffCsp, nosniff, referrer],
      },
      {
        source: "/inbox",
        headers: [staffCsp, nosniff, referrer],
      },
      {
        source: "/login",
        headers: [staffCsp, nosniff, referrer],
      },
      {
        source: "/sites",
        headers: [staffCsp, nosniff, referrer],
      },
      {
        source: "/knowledge",
        headers: [staffCsp, nosniff, referrer],
      },
      {
        source: "/settings",
        headers: [staffCsp, nosniff, referrer],
      },
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
    ]
  },
}

export default nextConfig
