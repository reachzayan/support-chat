import { describe, expect, test, vi } from "vitest"

import { fetchWidgetAncestors, widgetFrameAncestorsCsp } from "./widget-csp"

const LOVABLE = "https://sample-preview.example.com"
const SITE_KEY = "lovable-demo"
const PUBLIC_KEY = "a".repeat(64)
const SERVICE_SECRET = "c".repeat(64)

describe("widget frame-ancestors CSP", () => {
  test("keeps only exact canonical http origins", () => {
    expect(
      widgetFrameAncestorsCsp([
        LOVABLE,
        `${LOVABLE}/path`,
        "https://user@example.com",
        "https://evil.test csp-injection",
        "*",
      ]),
    ).toBe(`frame-ancestors ${LOVABLE}`)
  })

  test("refuses framing when no valid origin remains", () => {
    expect(widgetFrameAncestorsCsp([])).toBe("frame-ancestors 'none'")
    expect(widgetFrameAncestorsCsp(["*"])).toBe("frame-ancestors 'none'")
  })
})

describe("site-scoped widget ancestor fetch", () => {
  test("posts the exact public site identity and parent origin to the internal API", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ancestors: [LOVABLE] }),
    })

    await expect(
      fetchWidgetAncestors(
        fetcher,
        "http://127.0.0.1:8000",
        SERVICE_SECRET,
        SITE_KEY,
        PUBLIC_KEY,
        LOVABLE,
      ),
    ).resolves.toEqual([LOVABLE])

    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/internal/widget-frame-ancestors",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-SupportChat-Widget-CSP": SERVICE_SECRET,
        },
        body: JSON.stringify({
          site_key: SITE_KEY,
          public_key: PUBLIC_KEY,
          parent_origin: LOVABLE,
        }),
      }),
    )
  })

  test("fails closed without identity or service authentication", async () => {
    const fetcher = vi.fn()

    await expect(
      fetchWidgetAncestors(fetcher, "http://127.0.0.1:8000", "", SITE_KEY, PUBLIC_KEY, LOVABLE),
    ).resolves.toEqual([])
    await expect(
      fetchWidgetAncestors(fetcher, "http://127.0.0.1:8000", SERVICE_SECRET, "", "", LOVABLE),
    ).resolves.toEqual([])
    expect(fetcher).not.toHaveBeenCalled()
  })

  test("has no static fallback when the internal API fails", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("offline"))

    await expect(
      fetchWidgetAncestors(
        fetcher,
        "http://127.0.0.1:8000",
        SERVICE_SECRET,
        SITE_KEY,
        PUBLIC_KEY,
        LOVABLE,
      ),
    ).resolves.toEqual([])
  })
})
