import { readdirSync, statSync } from "node:fs"
import { join } from "node:path"

import { NextRequest } from "next/server"
import { describe, expect, test } from "vitest"

import { proxy, STAFF_PREFIXES } from "./proxy"

const PUBLIC_PAGE_PATHS = new Set(["/", "/widget", "/demo"])

const staffPagePaths = () => {
  const appDir = join(process.cwd(), "src/app")
  const paths: string[] = []
  const walk = (dir: string, prefix: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry)
      if (!statSync(full).isDirectory()) {
        if (entry === "page.tsx") {
          paths.push(prefix === "" ? "/" : prefix)
        }
        continue
      }
      const next = prefix === "" ? `/${entry}` : `${prefix}/${entry}`
      walk(full, next)
    }
  }
  walk(appDir, "")
  return paths.filter((pathname) => !PUBLIC_PAGE_PATHS.has(pathname))
}

const isStaffPath = (pathname: string) => {
  return STAFF_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

const requestFor = (url: string, host: string) => {
  return new NextRequest(url, { headers: { host } })
}

describe("host surface routing", () => {
  test("widget origin cannot reach staff routes", () => {
    const inbox = proxy(requestFor("http://widget.localhost:3000/inbox", "widget.localhost:3000"))
    const refresh = proxy(
      requestFor("http://widget.localhost:3000/auth/refresh", "widget.localhost:3000"),
    )
    expect(inbox.status).toBe(404)
    expect(refresh.status).toBe(404)
  })

  test("marketing host cannot reach staff inbox", () => {
    const inbox = proxy(requestFor("http://host.localhost:3000/inbox", "host.localhost:3000"))
    expect(inbox.status).toBe(404)
  })

  test("widget origin cannot reach canonical admin routes", () => {
    const inbox = proxy(
      requestFor("http://widget.localhost:3000/admin/inbox", "widget.localhost:3000"),
    )
    expect(inbox.status).toBe(404)
  })

  test("staff origin keeps inbox", () => {
    const inbox = proxy(requestFor("http://localhost:3000/inbox", "localhost:3000"))
    expect(inbox.status).toBe(200)
  })

  test("widget origin cannot reach handoff APIs", () => {
    const outcome = proxy(
      requestFor(
        "http://widget.localhost:3000/api/handoffs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/outcome",
        "widget.localhost:3000",
      ),
    )
    expect(outcome.status).toBe(404)
  })

  test("staff origin keeps handoff APIs", () => {
    const outcome = proxy(
      requestFor(
        "http://localhost:3000/api/handoffs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/outcome",
        "localhost:3000",
      ),
    )
    expect(outcome.status).toBe(200)
  })

  test("widget origin cannot reach settings", () => {
    const settings = proxy(
      requestFor("http://widget.localhost:3000/settings", "widget.localhost:3000"),
    )
    expect(settings.status).toBe(404)
  })

  test("widget origin cannot reach admin data console", () => {
    const data = proxy(
      requestFor("http://widget.localhost:3000/admin/data", "widget.localhost:3000"),
    )
    expect(data.status).toBe(404)
  })

  test("every staff page route is blocked on the widget host", () => {
    const uncovered = staffPagePaths().filter((pathname) => !isStaffPath(pathname))
    expect(uncovered).toEqual([])
  })
})
