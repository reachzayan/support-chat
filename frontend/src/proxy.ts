import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

import { fetchWidgetAncestors, widgetFrameAncestorsCsp } from "./lib/widget-csp"

const hostFromOrigin = (value: string | undefined) => {
  if (!value) {
    return ""
  }
  try {
    return new URL(value).host
  } catch {
    return ""
  }
}

const widgetHost = () => {
  return hostFromOrigin(process.env.NEXT_PUBLIC_WIDGET_ORIGIN) || "widget.localhost:3000"
}

const marketingHost = () => {
  return hostFromOrigin(process.env.NEXT_PUBLIC_MARKETING_HOST_ORIGIN) || "host.localhost:3000"
}

const apiOrigin = () => process.env.API_ORIGIN ?? "http://127.0.0.1:8000"

const cspServiceSecret = () => process.env.WIDGET_CSP_SERVICE_SECRET ?? ""

const clientIp = (request: NextRequest) => {
  const raw = request.headers.get("x-real-ip") ?? request.headers.get("x-forwarded-for") ?? ""
  return raw.split(",", 1)[0]?.trim().slice(0, 64) ?? ""
}

export const STAFF_PREFIXES = [
  "/admin",
  "/inbox",
  "/login",
  "/sites",
  "/knowledge",
  "/settings",
  "/auth",
  "/api/conversations",
  "/api/sites",
  "/api/articles",
  "/api/canned-replies",
  "/api/kb-sources",
  "/api/kb-pages",
  "/api/kb-chunks",
  "/api/handoffs",
  "/api/logs",
]

const isStaffPath = (pathname: string) => {
  return STAFF_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

const isStaffDocumentPath = (pathname: string) => {
  return (
    pathname === "/login" ||
    pathname.startsWith("/admin") ||
    pathname === "/inbox" ||
    pathname.startsWith("/inbox/") ||
    pathname === "/sites" ||
    pathname.startsWith("/sites/") ||
    pathname === "/knowledge" ||
    pathname.startsWith("/knowledge/") ||
    pathname === "/settings" ||
    pathname.startsWith("/settings/")
  )
}

const isWidgetOnlyPath = (pathname: string) => {
  return (
    pathname === "/widget" ||
    pathname === "/supportchat.js" ||
    pathname === "/api/public/widget-bootstrap"
  )
}

export const staffDocumentCsp = (nonce: string, api = apiOrigin()) => {
  const ws = api.replace(/^http/, "ws")
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "font-src 'self'",
    `connect-src 'self' ${api} ${ws}`,
    "frame-ancestors 'none'",
  ]
    .join("; ")
    .replace(/\s{2,}/g, " ")
    .trim()
}

const applyWidgetCsp = async (request: NextRequest, response: NextResponse) => {
  if (request.nextUrl.pathname !== "/widget") {
    return response
  }
  const siteKey = request.nextUrl.searchParams.get("site_key") ?? ""
  const publicKey = request.nextUrl.searchParams.get("public_key") ?? ""
  const parentOrigin = request.nextUrl.searchParams.get("parent_origin") ?? ""
  const origins = await fetchWidgetAncestors(
    fetch,
    apiOrigin(),
    cspServiceSecret(),
    siteKey,
    publicKey,
    parentOrigin,
    clientIp(request),
  )
  response.headers.set("Content-Security-Policy", widgetFrameAncestorsCsp(origins))
  response.headers.set("Cache-Control", "private, no-store")
  return response
}

export const proxy = async (request: NextRequest) => {
  const host = request.headers.get("host") ?? request.nextUrl.host
  const pathname = request.nextUrl.pathname
  if (host !== widgetHost() && isWidgetOnlyPath(pathname)) {
    return new NextResponse(null, { status: 404 })
  }
  if ((host === widgetHost() || host === marketingHost()) && isStaffPath(pathname)) {
    return new NextResponse(null, { status: 404 })
  }
  const requestHeaders = new Headers(request.headers)
  if (pathname === "/widget") {
    requestHeaders.set("x-supportchat-surface", "widget")
  }
  if (isStaffDocumentPath(pathname)) {
    const nonce = Buffer.from(crypto.randomUUID()).toString("base64")
    const csp = staffDocumentCsp(nonce)
    requestHeaders.set("x-nonce", nonce)
    requestHeaders.set("Content-Security-Policy", csp)
    const response = NextResponse.next({ request: { headers: requestHeaders } })
    response.headers.set("Content-Security-Policy", csp)
    return response
  }
  return applyWidgetCsp(request, NextResponse.next({ request: { headers: requestHeaders } }))
}
