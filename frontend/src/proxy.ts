import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

import {
  fetchWidgetAncestors,
  parentOriginFromReferer,
  widgetFrameAncestorsCsp,
} from "./lib/widget-csp"

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

const envFallback = () => {
  const raw = process.env.WIDGET_FRAME_ANCESTORS ?? process.env.APPROVED_FRAME_ANCESTORS ?? ""
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0 && !part.includes("*"))
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

const applyWidgetCsp = async (request: NextRequest, response: NextResponse) => {
  if (request.nextUrl.pathname !== "/widget") {
    return response
  }
  const parent = parentOriginFromReferer(request.headers.get("referer"))
  const origins = await fetchWidgetAncestors(fetch, apiOrigin(), parent, envFallback())
  response.headers.set("Content-Security-Policy", widgetFrameAncestorsCsp(origins))
  return response
}

export const proxy = async (request: NextRequest) => {
  const host = request.headers.get("host") ?? request.nextUrl.host
  const pathname = request.nextUrl.pathname
  if ((host === widgetHost() || host === marketingHost()) && isStaffPath(pathname)) {
    return new NextResponse(null, { status: 404 })
  }
  return applyWidgetCsp(request, NextResponse.next())
}
