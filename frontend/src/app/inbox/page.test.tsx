import { screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import InboxPage from "./page"

const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}))

describe("inbox session bootstrap", () => {
  beforeEach(() => {
    replace.mockReset()
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Not authenticated" }),
      }),
    )
  })

  test("redirects to login when refresh returns 401", async () => {
    renderWithProviders(<InboxPage />)
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(screen.queryByText("Inbox")).not.toBeInTheDocument()
  })
})
