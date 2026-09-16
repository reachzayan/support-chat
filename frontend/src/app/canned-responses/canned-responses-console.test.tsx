import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { CannedResponsesConsole } from "./canned-responses-console"

const EASY_SITE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

const response = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

const records = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    site_id: null,
    shortcut: "hours",
    body: "Most negative results are reported within 24–48 hours.",
    enabled: true,
    created_at: "2026-09-16T12:00:00Z",
    updated_at: "2026-09-16T12:00:00Z",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    site_id: EASY_SITE,
    shortcut: "privacy",
    body: "SampleSite privacy requests are answered by our specialists.",
    enabled: false,
    created_at: "2026-09-16T12:00:00Z",
    updated_at: "2026-09-16T12:00:00Z",
  },
]

const stubCannedResponsesFetch = () => {
  window.history.replaceState(null, "", "/admin/canned-responses")
  setAccessToken("staff-token")
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === "/api/canned-replies/library") {
        return response({ items: records })
      }
      if (url === "/api/sites") {
        return response({
          items: [
            {
              id: EASY_SITE,
              name: "SampleSite",
            },
          ],
        })
      }
      if (url === `/api/canned-replies/${records[1].id}` && init?.method === "PATCH") {
        return response({ ...records[1], enabled: true })
      }
      if (url === `/api/canned-replies/${records[0].id}` && init?.method === "DELETE") {
        return response(null, 204)
      }
      return response({ detail: "missing" }, 404)
    }),
  )
}

describe("canned responses console scope", () => {
  beforeEach(() => {
    stubCannedResponsesFetch()
  })

  test("shows only the selected website records and restores a disabled response after enable", async () => {
    const user = userEvent.setup()
    renderWithProviders(<CannedResponsesConsole />)

    await screen.findAllByText("#hours")
    await user.click(screen.getByLabelText("Scope"))
    await user.click(await screen.findByRole("option", { name: "SampleSite" }))

    expect(new URL(window.location.href).searchParams.get("scope")).toBe(EASY_SITE)
    const table = screen.getByRole("table")
    expect(within(table).queryByText("#hours")).not.toBeInTheDocument()
    expect(within(table).getByText("#privacy")).toBeInTheDocument()
    expect(within(table).getByText("Disabled")).toBeInTheDocument()

    await user.click(within(table).getByRole("switch", { name: "Enable #privacy" }))
    await waitFor(() => expect(within(table).getByText("Enabled")).toBeInTheDocument())
    const patchCall = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/canned-replies/${records[1].id}` &&
          (call[1] as RequestInit)?.method === "PATCH",
      )
    expect(patchCall).toBeDefined()
    if (!patchCall) throw new Error("expected canned-response update request")
    expect(JSON.parse(String((patchCall[1] as RequestInit).body))).toEqual({ enabled: true })
  })
})

describe("canned responses console editor", () => {
  beforeEach(() => {
    stubCannedResponsesFetch()
  })

  test("caps the shortcut field at 40 characters, matching the backend limit", async () => {
    renderWithProviders(<CannedResponsesConsole />)
    await screen.findAllByText("#hours")
    await userEvent.setup().click(screen.getByRole("button", { name: "Add response" }))

    const dialog = await screen.findByRole("dialog")
    const shortcutInput = within(dialog)
      .getAllByRole("textbox")
      .find((element) => element.tagName === "INPUT")
    if (!shortcutInput) throw new Error("expected shortcut input")
    expect(shortcutInput).toHaveAttribute("maxlength", "40")
  })

  test("removes a response after confirming delete", async () => {
    const user = userEvent.setup()
    renderWithProviders(<CannedResponsesConsole />)

    await screen.findAllByText("#hours")
    await user.click(screen.getByRole("button", { name: "Remove #hours" }))
    await user.click(await screen.findByRole("button", { name: "Remove response" }))

    await waitFor(() => expect(screen.queryByText("#hours")).not.toBeInTheDocument())
    const deleteCall = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/canned-replies/${records[0].id}` &&
          (call[1] as RequestInit)?.method === "DELETE",
      )
    expect(deleteCall).toBeDefined()
  })
})
