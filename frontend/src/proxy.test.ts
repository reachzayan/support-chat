import { readdirSync, statSync } from "node:fs"
import { join } from "node:path"

import { NextRequest } from "next/server"
import { afterEach, describe, expect, test, vi } from "vitest"

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
  test("widget origin cannot reach staff routes", async () => {
    const inbox = await proxy(
      requestFor("http://widget.localhost:3000/inbox", "widget.localhost:3000"),
    )
    const refresh = await proxy(
      requestFor("http://widget.localhost:3000/auth/refresh", "widget.localhost:3000"),
    )
    expect(inbox.status).toBe(404)
    expect(refresh.status).toBe(404)
  })

  test("marketing host cannot reach staff inbox", async () => {
    const inbox = await proxy(requestFor("http://host.localhost:3000/inbox", "host.localhost:3000"))
    expect(inbox.status).toBe(404)
  })

  test("widget origin cannot reach canonical admin routes", async () => {
    const inbox = await proxy(
      requestFor("http://widget.localhost:3000/admin/inbox", "widget.localhost:3000"),
    )
    expect(inbox.status).toBe(404)
  })

  test("staff origin keeps inbox", async () => {
    const inbox = await proxy(requestFor("http://localhost:3000/inbox", "localhost:3000"))
    expect(inbox.status).toBe(200)
  })

  test("widget origin cannot reach handoff APIs", async () => {
    const outcome = await proxy(
      requestFor(
        "http://widget.localhost:3000/api/handoffs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/outcome",
        "widget.localhost:3000",
      ),
    )
    expect(outcome.status).toBe(404)
  })

  test("staff origin keeps handoff APIs", async () => {
    const outcome = await proxy(
      requestFor(
        "http://localhost:3000/api/handoffs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/outcome",
        "localhost:3000",
      ),
    )
    expect(outcome.status).toBe(200)
  })

  test("widget origin cannot reach settings", async () => {
    const settings = await proxy(
      requestFor("http://widget.localhost:3000/settings", "widget.localhost:3000"),
    )
    expect(settings.status).toBe(404)
  })

  test("widget origin cannot reach admin data console", async () => {
    const data = await proxy(
      requestFor("http://widget.localhost:3000/admin/data", "widget.localhost:3000"),
    )
    expect(data.status).toBe(404)
  })

  test("every staff page route is blocked on the widget host", () => {
    const uncovered = staffPagePaths().filter((pathname) => !isStaffPath(pathname))
    expect(uncovered).toEqual([])
  })
})

describe("widget document CSP", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  test("allows only the embedding website even if the API lists others", async () => {
    const lovable = "https://sample-preview.example.com"
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ancestors: [lovable, "https://host.deployment.example.com"],
        }),
      }),
    )
    const response = await proxy(
      new NextRequest("http://widget.localhost:3000/widget", {
        headers: {
          host: "widget.localhost:3000",
          referer: `${lovable}/pricing`,
        },
      }),
    )
    expect(response.headers.get("Content-Security-Policy")).toBe(`frame-ancestors ${lovable}`)
    expect(response.headers.get("Content-Security-Policy")).not.toContain("sslip")
  })
})
