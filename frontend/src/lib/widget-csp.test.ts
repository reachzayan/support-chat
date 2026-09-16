import { describe, expect, test, vi } from "vitest"

import {
  fetchWidgetAncestors,
  parentOriginFromReferer,
  widgetFrameAncestorsCsp,
} from "./widget-csp"

const LOVABLE = "https://sample-preview.example.com"
const LOCAL = "http://localhost:3000"
const SSLIP_HOST = "https://host.deployment.example.com"

describe("widget frame-ancestors CSP", () => {
  test("a website only allows itself as the ancestor", () => {
    expect(widgetFrameAncestorsCsp([LOVABLE])).toBe(`frame-ancestors ${LOVABLE}`)
  })

  test("strips wildcards and refuses framing when nothing remains", () => {
    expect(widgetFrameAncestorsCsp(["*"])).toBe("frame-ancestors 'none'")
    expect(widgetFrameAncestorsCsp([])).toBe("frame-ancestors 'none'")
  })
})

describe("parent origin from referer", () => {
  test("keeps the embedding website origin and drops the path", () => {
    expect(parentOriginFromReferer(`${LOVABLE}/pricing`)).toBe(LOVABLE)
  })

  test("rejects missing or invalid referers", () => {
    expect(parentOriginFromReferer(null)).toBe("")
    expect(parentOriginFromReferer("not-a-url")).toBe("")
  })
})

describe("widget ancestor fetch", () => {
  test("asks only for the embedding website and ignores other sites in the payload", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ancestors: [LOVABLE, SSLIP_HOST] }),
    })

    await expect(
      fetchWidgetAncestors(fetcher, "http://127.0.0.1:8000", LOVABLE, [LOCAL]),
    ).resolves.toEqual([LOVABLE])
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `http://127.0.0.1:8000/api/public/widget-frame-ancestors?parent=${encodeURIComponent(LOVABLE)}`,
    )
  })

  test("does not fall back to other websites when the endpoint fails", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) })

    await expect(
      fetchWidgetAncestors(fetcher, "http://127.0.0.1:8000", LOVABLE, [LOCAL]),
    ).resolves.toEqual([])
  })

  test("allows a platform host from env only when that host is the parent", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("offline"))

    await expect(
      fetchWidgetAncestors(fetcher, "http://127.0.0.1:8000", LOCAL, [LOCAL]),
    ).resolves.toEqual([LOCAL])
  })
})
