import { beforeEach, describe, expect, test, vi } from "vitest"

vi.mock("next/navigation", () => ({
  usePathname: () => "/widget",
}))

import { StaffSessionBootstrap } from "@/components/staff-session"
import { renderWithProviders } from "@/test/render"

describe("widget staff isolation", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("does not call staff auth from the widget path", () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    renderWithProviders(<StaffSessionBootstrap />)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
