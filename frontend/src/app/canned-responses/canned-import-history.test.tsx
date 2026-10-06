import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { CannedResponsesConsole } from "./canned-responses-console"

const batch = {
  id: 7,
  filename: "approved.csv",
  uploaded_at: "2026-10-06T12:00:00Z",
  uploaded_by_name: "Zayan Khan",
  created: 1,
  updated: 0,
  skipped: 0,
}
beforeEach(() => {
  setAccessToken("staff-token")
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const body =
        url === "/api/canned-replies/library" || url === "/api/sites"
          ? { items: [] }
          : url.startsWith("/api/canned-replies/imports?")
            ? { items: [batch], has_more: false }
            : url.startsWith("/api/canned-replies/imports/7?")
              ? {
                  batch,
                  rows: [
                    {
                      row_number: 1,
                      reply_id: "reply",
                      action: "create",
                      snapshot: {
                        shortcut: "results",
                        body: "Results take two days.",
                        site_id: null,
                        reason: null,
                      },
                    },
                  ],
                  has_more: false,
                }
              : null
      return { ok: body !== null, status: body === null ? 404 : 200, json: async () => body }
    }),
  )
})

test("opens upload history and reviews the saved wording for one file", async () => {
  renderWithProviders(<CannedResponsesConsole />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole("button", { name: "Upload history" }))
  const dialog = screen.getByRole("dialog", { name: "CSV upload history" })
  await user.click(
    await within(dialog).findByRole("button", { name: "View upload 7: approved.csv" }),
  )
  expect(await within(dialog).findByText("Results take two days.")).toBeInTheDocument()
  expect(within(dialog).getByText("#results")).toBeInTheDocument()
  expect(within(dialog).getByText("Zayan Khan")).toBeInTheDocument()
  await user.keyboard("{Escape}")
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  expect(screen.getByRole("heading", { name: "Canned responses" })).toBeInTheDocument()
})
