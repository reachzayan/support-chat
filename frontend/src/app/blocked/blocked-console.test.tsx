import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { BlockedConsole } from "./blocked-console"

const BLOCKED = {
  id: "block-1",
  site_id: "samplesite",
  site_name: "SampleSite",
  ip: "203.0.113.40",
  email: "ada@example.com",
  phone: null,
  created_by_name: "Alex Morgan",
  created_at: "2026-09-29T12:00:00Z",
}

describe("blocked console", () => {
  beforeEach(() => {
    setAccessToken("staff-token")
  })

  test("lists a blocked visitor and unblocks them", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === "/api/visitor-blocks" && !init?.method) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ items: [BLOCKED] }),
        }
      }
      if (url === `/api/visitor-blocks/${BLOCKED.id}` && init?.method === "DELETE") {
        return { ok: true, status: 204, json: async () => ({}) }
      }
      return { ok: false, status: 404, json: async () => ({}) }
    })
    vi.stubGlobal("fetch", fetchMock)
    renderWithProviders(<BlockedConsole />)
    expect(await screen.findByText("ada@example.com")).toBeInTheDocument()
    expect(screen.getByText("SampleSite")).toBeInTheDocument()
    expect(screen.getByText("Alex Morgan")).toBeInTheDocument()
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Unblock visitor on SampleSite" }))
    await waitFor(() => expect(screen.getByText("Visitor unblocked.")).toBeInTheDocument())
    expect(screen.getByText("No blocked visitors")).toBeInTheDocument()
  })
})
