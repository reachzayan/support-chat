/* oxlint-disable react-perf/jsx-no-new-function-as-prop, eslint/max-lines-per-function -- Test doubles and preview stubs are created per case. */

import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { ImportDialog } from "./canned-import-dialog"

const noopImported = async () => undefined
const EASY_SITE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const BG_SITE = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
const SITES = [
  { id: EASY_SITE, name: "SampleSite" },
  { id: BG_SITE, name: "Sample Services" },
]

const INSTANT_CHECK_BODY = "Instant Check orders are not handled in this chat."
const UPDATED_HOURS = "SampleSite results are usually ready in one business day."
const DISCOUNT_BODY = "Use code 10BGC at checkout for 10 percent off sample services."

const jsonResponse = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

const previewRow = (overrides: Record<string, unknown>) => ({
  action: "create",
  reason: null,
  livechat_id: 1,
  group: 6,
  group_name: "SampleSite",
  shortcut: "hours",
  aliases: [],
  bot_eligible: true,
  disable_reason: null,
  suggestion_event: null,
  excerpt: "Most negative results are reported within 24-48 hours.",
  ...overrides,
})

const renderImport = () =>
  renderWithProviders(
    <ImportDialog open onClose={vi.fn()} onImported={noopImported} sites={SITES} />,
  )

const chooseCsv = async () => {
  const user = userEvent.setup()
  const file = new File(["id,text,tags,group"], "canned.csv", { type: "text/csv" })
  await user.upload(screen.getByLabelText("LiveChat canned responses CSV"), file)
  return user
}

describe("canned import dialog", () => {
  beforeEach(() => {
    setAccessToken("staff-token")
    vi.unstubAllGlobals()
  })

  test("asks for a CSV without listing LiveChat group numbers", () => {
    renderImport()

    expect(screen.getByText("Import LiveChat canned responses")).toBeInTheDocument()
    expect(screen.getByLabelText("LiveChat canned responses CSV")).toBeInTheDocument()
    expect(screen.queryByText(/Group 0/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Instant Check/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/id, text, tags, group/i)).not.toBeInTheDocument()
  })

  test("closes when the dimmed area outside the dialog is clicked", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderWithProviders(
      <ImportDialog open onClose={onClose} onImported={noopImported} sites={SITES} />,
    )
    expect(screen.getByText("Import LiveChat canned responses")).toBeInTheDocument()

    const overlay = document.querySelector("[data-slot='dialog-overlay']")
    if (!overlay) throw new Error("expected dialog overlay")
    await user.click(overlay)

    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})

describe("canned import preview decisions", () => {
  beforeEach(() => {
    setAccessToken("staff-token")
    vi.unstubAllGlobals()
  })

  test("offers Instant Check rows a website or discard instead of hiding the copy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/canned-replies/import/preview") {
          return jsonResponse({
            created: 0,
            updated: 0,
            skipped: 0,
            rows: [
              previewRow({
                action: "unmapped",
                livechat_id: 501,
                group: 5,
                group_name: "Instant Check",
                shortcut: "instant-check",
                excerpt: INSTANT_CHECK_BODY,
                reason: "The LiveChat group 5 is Instant Check, which is not a SupportChat site.",
              }),
            ],
          })
        }
        return jsonResponse({ detail: "missing" }, 404)
      }),
    )
    renderImport()
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))

    expect(
      await screen.findByText(
        "The LiveChat group 5 is Instant Check, which is not a SupportChat site.",
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(INSTANT_CHECK_BODY)).toBeInTheDocument()
    expect(screen.getByLabelText("Add Instant Check responses to")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Discard Instant Check responses" }),
    ).toBeInTheDocument()
    await user.click(screen.getByLabelText("Add Instant Check responses to"))
    expect(await screen.findByRole("option", { name: "SampleSite" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Sample Services" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "General — all websites" })).toBeInTheDocument()
  })

  test("imports Instant Check rows onto the website staff choose", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url === "/api/canned-replies/import/preview") {
        return jsonResponse({
          created: 0,
          updated: 0,
          skipped: 0,
          rows: [
            previewRow({
              action: "unmapped",
              livechat_id: 501,
              group: 5,
              group_name: "Instant Check",
              shortcut: "instant-check",
              excerpt: INSTANT_CHECK_BODY,
              reason: "The LiveChat group 5 is Instant Check, which is not a SupportChat site.",
            }),
          ],
        })
      }
      if (url === "/api/canned-replies/import") {
        return jsonResponse({ created: 1, updated: 0, skipped: 0 })
      }
      return jsonResponse({ detail: "missing" }, 404)
    })
    vi.stubGlobal("fetch", fetchMock)
    renderImport()
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))
    await screen.findByText(INSTANT_CHECK_BODY)
    await user.click(screen.getByLabelText("Add Instant Check responses to"))
    await user.click(await screen.findByRole("option", { name: "SampleSite" }))
    await user.click(screen.getByRole("button", { name: "Import responses" }))

    await waitFor(() => {
      const commit = fetchMock.mock.calls.find(
        (call) => String(call[0]) === "/api/canned-replies/import",
      )
      expect(commit).toBeDefined()
      if (!commit) throw new Error("expected import commit")
      const body = commit[1]?.body
      if (!(body instanceof FormData)) throw new Error("expected multipart import")
      expect(JSON.parse(String(body.get("decisions")))).toEqual({
        discard_ids: [],
        remap_groups: { "5": EASY_SITE },
      })
    })
  })

  test("lets staff keep or update selected duplicate responses", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url === "/api/canned-replies/import/preview") {
        return jsonResponse({
          created: 0,
          updated: 1,
          skipped: 0,
          rows: [
            previewRow({
              action: "update",
              livechat_id: 200,
              shortcut: "hours",
              excerpt: UPDATED_HOURS,
            }),
          ],
        })
      }
      if (url === "/api/canned-replies/import") {
        return jsonResponse({ created: 0, updated: 0, skipped: 1 })
      }
      return jsonResponse({ detail: "missing" }, 404)
    })
    vi.stubGlobal("fetch", fetchMock)
    renderImport()
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))

    expect(await screen.findByText(UPDATED_HOURS)).toBeInTheDocument()
    const checkbox = screen.getByRole("checkbox", { name: "Update #hours" })
    expect(checkbox).toBeChecked()
    await user.click(screen.getByRole("button", { name: "Select none" }))
    expect(checkbox).not.toBeChecked()
    await user.click(screen.getByRole("button", { name: "Import responses" }))

    await waitFor(() => {
      const commit = fetchMock.mock.calls.find(
        (call) => String(call[0]) === "/api/canned-replies/import",
      )
      expect(commit).toBeDefined()
      if (!commit) throw new Error("expected import commit")
      const body = commit[1]?.body
      if (!(body instanceof FormData)) throw new Error("expected multipart import")
      expect(JSON.parse(String(body.get("decisions")))).toEqual({
        discard_ids: [200],
        remap_groups: {},
      })
    })
  })

  test("shows discount-code copy that will stay off the bot", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/canned-replies/import/preview") {
          return jsonResponse({
            created: 1,
            updated: 0,
            skipped: 0,
            rows: [
              previewRow({
                livechat_id: 310,
                shortcut: "10bgc",
                excerpt: DISCOUNT_BODY,
                bot_eligible: false,
                disable_reason: "Discount code — not available to the bot.",
              }),
            ],
          })
        }
        return jsonResponse({ detail: "missing" }, 404)
      }),
    )
    renderImport()
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))

    expect(await screen.findByText("Discount code — not available to the bot.")).toBeInTheDocument()
    expect(screen.getByText(DISCOUNT_BODY)).toBeInTheDocument()
  })
})
