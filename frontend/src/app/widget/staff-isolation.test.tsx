import { beforeEach, describe, expect, test, vi } from "vitest"

vi.mock("next/navigation", () => ({
  usePathname: () => "/widget",
  useSearchParams: () => new URLSearchParams("site_key=demo"),
}))

import { renderWithProviders } from "@/test/render"

describe("widget staff isolation", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("widget surface does not call staff auth refresh on mount", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    const { default: WidgetPage } = await import("@/app/widget/page")
    renderWithProviders(<WidgetPage />)
    const authCalls = fetchMock.mock.calls.filter((call) => String(call[0]).includes("/auth/"))
    expect(authCalls).toHaveLength(0)
  })
})
