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

  test("staff and marketing hosts cannot serve widget-only surfaces", async () => {
    const requests = [
      requestFor("http://localhost:3000/widget", "localhost:3000"),
      requestFor("http://localhost:3000/supportchat.js", "localhost:3000"),
      requestFor("http://host.localhost:3000/api/public/widget-bootstrap", "host.localhost:3000"),
    ]

    const responses = await Promise.all(requests.map((request) => proxy(request)))
    expect(responses.map((response) => response.status)).toEqual([404, 404, 404])
  })

  test("every staff page route is blocked on the widget host", () => {
    const uncovered = staffPagePaths().filter((pathname) => !isStaffPath(pathname))
    expect(uncovered).toEqual([])
  })
})

describe("visitor block API routing", () => {
  test("widget origin cannot reach visitor block APIs", async () => {
    const listed = await proxy(
      requestFor("http://widget.localhost:3000/api/visitor-blocks", "widget.localhost:3000"),
    )
    expect(listed.status).toBe(404)
  })

  test("staff origin keeps visitor block APIs", async () => {
    const listed = await proxy(
      requestFor("http://localhost:3000/api/visitor-blocks", "localhost:3000"),
    )
    expect(listed.status).toBe(200)
  })
})

describe("widget document CSP", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    delete process.env.WIDGET_CSP_SERVICE_SECRET
  })

  test("uses the site-scoped query when Referer is suppressed", async () => {
    const lovable = "https://sample-preview.example.com"
    const publicKey = "a".repeat(64)
    process.env.WIDGET_CSP_SERVICE_SECRET = "c".repeat(64)
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ancestors: [lovable] }),
    })
    vi.stubGlobal("fetch", fetcher)
    const response = await proxy(
      new NextRequest(
        `http://widget.localhost:3000/widget?site_key=lovable-demo&public_key=${publicKey}&parent_origin=${encodeURIComponent(lovable)}`,
        { headers: { host: "widget.localhost:3000", "x-real-ip": "203.0.113.40" } },
      ),
    )
    expect(response.headers.get("Content-Security-Policy")).toBe(`frame-ancestors ${lovable}`)
    expect(fetcher.mock.calls[0]?.[1]?.headers).toMatchObject({
      "X-SupportChat-Client-IP": "203.0.113.40",
    })
  })

  test("fails closed when the widget URL has no complete site identity", async () => {
    const fetcher = vi.fn()
    vi.stubGlobal("fetch", fetcher)

    const response = await proxy(
      new NextRequest("http://widget.localhost:3000/widget", {
        headers: { host: "widget.localhost:3000" },
      }),
    )

    expect(response.headers.get("Content-Security-Policy")).toBe("frame-ancestors 'none'")
    expect(fetcher).not.toHaveBeenCalled()
  })
})
