/* oxlint-disable react-perf/jsx-no-new-function-as-prop, eslint/max-lines-per-function -- Test doubles and preview stubs are created per case. */

import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { ImportDialog } from "./canned-import-dialog"

const noopImported = async () => undefined
const EASY_SITE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const BG_SITE = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
const DATA_SITE = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
const SITES = [
  { id: EASY_SITE, name: "SampleSite" },
  { id: BG_SITE, name: "Sample Services" },
]
const EC2_SITES = [
  { id: EASY_SITE, name: "SampleSite" },
  { id: DATA_SITE, name: "Data Solutions" },
]

const INSTANT_CHECK_BODY = "Instant Check orders are not handled in this chat."
const BG_CHECKS_BODY = "Background check packages start at $19.95."
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
  site_id: EASY_SITE,
  shortcut: "hours",
  aliases: [],
  bot_eligible: true,
  disable_reason: null,
  suggestion_event: null,
  livechat_website: "sample-site.example.com",
  excerpt: "Most negative results are reported within 24-48 hours.",
  ...overrides,
})

const renderImport = (sites = SITES) =>
  renderWithProviders(
    <ImportDialog open onClose={vi.fn()} onImported={noopImported} sites={sites} />,
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

  test("lets staff drag the corner to enlarge the import dialog", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1400 })
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 1100 })
    renderImport()
    const dialog = screen.getByRole("dialog", { name: "Import LiveChat canned responses" })
    const handle = screen.getByRole("button", { name: "Resize dialog" })
    expect(Number.parseFloat(dialog.style.width || "0")).toBe(768)
    expect(Number.parseFloat(dialog.style.height || "0")).toBe(720)

    fireEvent.pointerDown(handle, { button: 0, clientX: 700, clientY: 500 })
    window.dispatchEvent(
      new PointerEvent("pointermove", { clientX: 860, clientY: 620, buttons: 1, bubbles: true }),
    )
    window.dispatchEvent(
      new PointerEvent("pointerup", { clientX: 860, clientY: 620, bubbles: true }),
    )

    // Avg of (768+160)/768 and (720+120)/720 is 1.1875 → 912×855 with locked aspect.
    await waitFor(() => {
      expect(Number.parseFloat(dialog.style.width || "0")).toBe(912)
      expect(Number.parseFloat(dialog.style.height || "0")).toBe(855)
    })
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
                site_id: null,
                shortcut: "instant-check",
                excerpt: INSTANT_CHECK_BODY,
                livechat_website: "365instantcheck.com",
                reason: null,
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

    expect(await screen.findByText("LiveChat group 5 · Instant Check")).toBeInTheDocument()
    expect(screen.getByText("365instantcheck.com")).toBeInTheDocument()
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

  test("asks which SupportChat website each LiveChat group belongs to", async () => {
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
                livechat_id: 200,
                group: 6,
                group_name: "SampleSite",
                site_id: EASY_SITE,
                livechat_website: "sample-site.example.com",
                excerpt: "Most negative results are reported within 24-48 hours.",
              }),
              previewRow({
                action: "unmapped",
                livechat_id: 410,
                group: 4,
                group_name: "Sample Services",
                site_id: null,
                shortcut: "packages",
                excerpt: BG_CHECKS_BODY,
                livechat_website: "sample-services.example.com",
                reason: null,
              }),
              previewRow({
                action: "unmapped",
                livechat_id: 501,
                group: 5,
                group_name: "Instant Check",
                site_id: null,
                shortcut: "instant-check",
                excerpt: INSTANT_CHECK_BODY,
                livechat_website: "365instantcheck.com",
                reason: null,
              }),
            ],
          })
        }
        return jsonResponse({ detail: "missing" }, 404)
      }),
    )
    renderImport(EC2_SITES)
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))

    expect(await screen.findByText("LiveChat group 6 · SampleSite")).toBeInTheDocument()
    expect(screen.getByText("sample-site.example.com")).toBeInTheDocument()
    expect(screen.getByText("LiveChat group 4 · Sample Services")).toBeInTheDocument()
    expect(screen.getByText("sample-services.example.com")).toBeInTheDocument()
    expect(screen.getByText("LiveChat group 5 · Instant Check")).toBeInTheDocument()
    expect(screen.getByText("365instantcheck.com")).toBeInTheDocument()
    expect(screen.getByText(BG_CHECKS_BODY)).toBeInTheDocument()
    expect(screen.getByText(INSTANT_CHECK_BODY)).toBeInTheDocument()
    expect(screen.getByLabelText("Add SampleSite responses to")).toBeInTheDocument()
    expect(screen.getByLabelText("Add Sample Services responses to")).toBeInTheDocument()
    expect(screen.getByLabelText("Add Instant Check responses to")).toBeInTheDocument()
    await user.click(screen.getByLabelText("Add Sample Services responses to"))
    expect(await screen.findByRole("option", { name: "SampleSite" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Data Solutions" })).toBeInTheDocument()
    expect(screen.queryByRole("option", { name: "Sample Services" })).not.toBeInTheDocument()
  })

  test("imports Sample Services onto Data Solutions after staff choose that website", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url === "/api/canned-replies/import/preview") {
        return jsonResponse({
          created: 1,
          updated: 0,
          skipped: 0,
          rows: [
            previewRow({
              livechat_id: 200,
              group: 6,
              group_name: "SampleSite",
              site_id: EASY_SITE,
              livechat_website: "sample-site.example.com",
            }),
            previewRow({
              action: "unmapped",
              livechat_id: 410,
              group: 4,
              group_name: "Sample Services",
              site_id: null,
              shortcut: "packages",
              excerpt: BG_CHECKS_BODY,
              livechat_website: "sample-services.example.com",
              reason: null,
            }),
            previewRow({
              action: "unmapped",
              livechat_id: 501,
              group: 5,
              group_name: "Instant Check",
              site_id: null,
              shortcut: "instant-check",
              excerpt: INSTANT_CHECK_BODY,
              livechat_website: "365instantcheck.com",
              reason: null,
            }),
          ],
        })
      }
      if (url === "/api/canned-replies/import") {
        return jsonResponse({ created: 2, updated: 0, skipped: 0 })
      }
      return jsonResponse({ detail: "missing" }, 404)
    })
    vi.stubGlobal("fetch", fetchMock)
    renderImport(EC2_SITES)
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))
    await screen.findByText(BG_CHECKS_BODY)
    expect(
      screen.getByText("Choose a website for Sample Services, or discard those responses."),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Choose a website for Instant Check, or discard those responses."),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import responses" })).toBeDisabled()
    await user.click(screen.getByLabelText("Add Sample Services responses to"))
    await user.click(await screen.findByRole("option", { name: "Data Solutions" }))
    expect(
      screen.queryByText("Choose a website for Sample Services, or discard those responses."),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText("Choose a website for Instant Check, or discard those responses."),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import responses" })).toBeDisabled()
    await user.click(screen.getByLabelText("Add Instant Check responses to"))
    await user.click(await screen.findByRole("option", { name: "Data Solutions" }))
    expect(screen.getByRole("button", { name: "Import responses" })).toBeEnabled()
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
        remap_groups: { "4": DATA_SITE, "5": DATA_SITE, "6": EASY_SITE },
      })
    })
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
              livechat_website: "365instantcheck.com",
              reason: null,
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

    expect(await screen.findByRole("checkbox", { name: "Update #hours" })).toBeInTheDocument()
    const checkbox = screen.getByRole("checkbox", { name: "Update #hours" })
    expect(checkbox).toBeChecked()
    expect(screen.getAllByText(UPDATED_HOURS).length).toBeGreaterThan(0)
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
        remap_groups: { "6": EASY_SITE },
      })
    })
  })

  test("lists General responses and marks agent-disabled ones with a pill", async () => {
    const generalBody = "Can I help you with anything else?"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/canned-replies/import/preview") {
          return jsonResponse({
            created: 2,
            updated: 0,
            skipped: 0,
            rows: [
              previewRow({
                livechat_id: 14,
                group: 0,
                group_name: "General",
                site_id: null,
                shortcut: "help",
                excerpt: generalBody,
                livechat_website: null,
                bot_eligible: false,
                disable_reason: "Conversational prompt — not available to the bot.",
              }),
              previewRow({
                livechat_id: 310,
                group: 0,
                group_name: "General",
                site_id: null,
                shortcut: "10bgc",
                excerpt: DISCOUNT_BODY,
                livechat_website: null,
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

    expect(await screen.findByText("LiveChat group 0 · General")).toBeInTheDocument()
    expect(screen.getByText(generalBody)).toBeInTheDocument()
    expect(screen.getByText(DISCOUNT_BODY)).toBeInTheDocument()
    expect(screen.getAllByText("Agent Disabled")).toHaveLength(2)
    expect(screen.queryByText("Not available to the bot")).not.toBeInTheDocument()
    expect(screen.queryByText(/responses in this LiveChat website/i)).not.toBeInTheDocument()
  })

  test("turns Instant Check skip rows into a mappable LiveChat group", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/canned-replies/import/preview") {
          return jsonResponse({
            created: 0,
            updated: 0,
            skipped: 2,
            rows: [
              previewRow({
                action: "skip",
                livechat_id: 501,
                group: 5,
                group_name: "Instant Check",
                site_id: null,
                shortcut: "",
                excerpt: INSTANT_CHECK_BODY,
                livechat_website: null,
                reason: "LiveChat group 5 is Instant Check, which is not a SupportChat website.",
              }),
              previewRow({
                action: "skip",
                livechat_id: 502,
                group: 5,
                group_name: "Instant Check",
                site_id: null,
                shortcut: "",
                excerpt: "Are you finding the search results you're looking for?",
                livechat_website: null,
                reason: "LiveChat group 5 is Instant Check, which is not a SupportChat website.",
              }),
            ],
          })
        }
        return jsonResponse({ detail: "missing" }, 404)
      }),
    )
    renderImport(EC2_SITES)
    const user = await chooseCsv()
    await user.click(screen.getByRole("button", { name: "Preview" }))

    expect(await screen.findByText("LiveChat group 5 · Instant Check")).toBeInTheDocument()
    expect(screen.getByText("365instantcheck.com")).toBeInTheDocument()
    expect(screen.getByText(INSTANT_CHECK_BODY)).toBeInTheDocument()
    expect(screen.getByLabelText("Add Instant Check responses to")).toBeInTheDocument()
    expect(screen.queryByText("Could not import")).not.toBeInTheDocument()
  })
})
