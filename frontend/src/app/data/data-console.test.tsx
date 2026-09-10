import { screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { DataConsole } from "./data-console"

describe("data console", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({}),
      }),
    )
  })

  test("shows a load error instead of the empty submissions state", async () => {
    renderWithProviders(<DataConsole />)
    await waitFor(() => expect(screen.getByText("Could not load submissions.")).toBeInTheDocument())
    expect(screen.queryByText("No form submissions yet")).not.toBeInTheDocument()
  })
})
