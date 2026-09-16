import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

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

export const proxy = (request: NextRequest) => {
  const host = request.headers.get("host") ?? request.nextUrl.host
  const pathname = request.nextUrl.pathname
  if ((host === widgetHost() || host === marketingHost()) && isStaffPath(pathname)) {
    return new NextResponse(null, { status: 404 })
  }
  return NextResponse.next()
}
