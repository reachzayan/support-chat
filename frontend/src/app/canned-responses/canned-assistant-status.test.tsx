import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { CannedResponsesConsole } from "./canned-responses-console"

const HOURS = "11111111-1111-4111-8111-111111111111"
const HELLO = "22222222-2222-4222-8222-222222222222"
const DOT = "33333333-3333-4333-8333-333333333333"
const DER_WHAT_IS = "44444444-4444-4444-8444-444444444444"
const DER_YES = "55555555-5555-4555-8555-555555555555"
const INTERPRETATION = "66666666-6666-4666-8666-666666666666"
const FILL_IN_REASON = "Has fill-in fields — not available to the bot."

const record = (id: string, shortcut: string, overrides: Record<string, unknown> = {}) => ({
  id,
  site_id: null,
  shortcut,
  body: `Approved wording for ${shortcut}.`,
  enabled: true,
  aliases: [] as string[],
  external_id: null,
  suggestion_event: null,
  bot_eligible: true,
  follows_id: null,
  hands_off: false,
  bot_block_reason: null,
  created_at: "2026-09-16T12:00:00Z",
  updated_at: "2026-09-16T12:00:00Z",
  ...overrides,
})

const library = [
  record(HOURS, "hours"),
  record(HELLO, "hello", { bot_eligible: false }),
  record(DOT, "dot_agency", { bot_block_reason: FILL_IN_REASON }),
  record(DER_WHAT_IS, "der_what_is"),
  record(DER_YES, "der_yes_followup", { follows_id: DER_WHAT_IS }),
  record(INTERPRETATION, "interpretation", { hands_off: true }),
]

const response = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

const stubFetch = () => {
  window.history.replaceState(null, "", "/admin/canned-responses")
  setAccessToken("staff-token")
  const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === "/api/canned-replies/library") return response({ items: library })
    if (url === "/api/sites") return response({ items: [] })
    if (init?.method === "PATCH") {
      const saved = library.find((row) => url.endsWith(row.id))
      return response({ ...saved, ...JSON.parse(String(init.body)) })
    }
    return response({ detail: "missing" }, 404)
  })
  vi.stubGlobal("fetch", fetchStub)
  return fetchStub
}

const rowOf = async (shortcut: string) => {
  const table = await screen.findByRole("table")
  const cell = within(table).getByText(`#${shortcut}`)
  const row = cell.closest("tr")
  if (!row) throw new Error(`no table row for #${shortcut}`)
  return row
}

describe("canned responses: what the assistant can use", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    stubFetch()
  })

  test("shows, per row, whether the assistant can use it and why not", async () => {
    renderWithProviders(<CannedResponsesConsole />)

    expect(within(await rowOf("hours")).getByText("Assistant")).toBeInTheDocument()
    expect(within(await rowOf("hello")).getByText("Staff only")).toBeInTheDocument()
    const blocked = await rowOf("dot_agency")
    expect(within(blocked).getByText("Blocked")).toBeInTheDocument()
    expect(within(blocked).getByText(FILL_IN_REASON)).toBeInTheDocument()
  })

  test("shows which script a follow-up answers and which scripts call a specialist", async () => {
    renderWithProviders(<CannedResponsesConsole />)

    expect(
      within(await rowOf("der_yes_followup")).getByText("Only after #der_what_is"),
    ).toBeVisible()
    expect(within(await rowOf("interpretation")).getByText("Connects a specialist")).toBeVisible()
    expect(within(await rowOf("hours")).queryByText(/Only after|Connects a specialist/)).toBeNull()
  })

  test("filters the library by what the assistant can do", async () => {
    const user = userEvent.setup()
    renderWithProviders(<CannedResponsesConsole />)
    await rowOf("hours")

    await user.click(screen.getByLabelText("Assistant"))
    await user.click(await screen.findByRole("option", { name: "Staff only" }))
    const table = await screen.findByRole("table")
    await waitFor(() => expect(within(table).queryByText("#hours")).not.toBeInTheDocument())
    expect(within(table).getByText("#hello")).toBeInTheDocument()

    await user.click(screen.getByLabelText("Assistant"))
    await user.click(await screen.findByRole("option", { name: "Blocked" }))
    await waitFor(() => expect(within(table).queryByText("#hello")).not.toBeInTheDocument())
    expect(within(table).getByText("#dot_agency")).toBeInTheDocument()
  })
})

describe("canned responses: editor fields", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("saves the script a reply follows and the hand-off switch", async () => {
    const user = userEvent.setup()
    const fetchStub = stubFetch()
    renderWithProviders(<CannedResponsesConsole />)

    await user.click(within(await rowOf("der_yes_followup")).getByRole("button", { name: "Edit" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(
      within(dialog).getByRole("switch", { name: /^Connect a specialist after sending/ }),
    )
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    const patch = fetchStub.mock.calls.find(
      ([url, init]) => String(url).endsWith(DER_YES) && init?.method === "PATCH",
    )
    expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({
      follows_id: DER_WHAT_IS,
      hands_off: true,
    })
  })

  test("offers only other scripts to follow, and can clear the link", async () => {
    const user = userEvent.setup()
    const fetchStub = stubFetch()
    renderWithProviders(<CannedResponsesConsole />)

    await user.click(within(await rowOf("der_yes_followup")).getByRole("button", { name: "Edit" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByLabelText("Only after"))
    expect(screen.queryByRole("option", { name: "#der_yes_followup" })).toBeNull()
    expect(await screen.findByRole("option", { name: "#der_what_is" })).toBeInTheDocument()
    await user.click(await screen.findByRole("option", { name: "Any time" }))
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    const patch = fetchStub.mock.calls.find(
      ([url, init]) => String(url).endsWith(DER_YES) && init?.method === "PATCH",
    )
    expect(JSON.parse(String(patch?.[1]?.body)).follows_id).toBeNull()
  })

  test("tells staff why the assistant ignores a switched-on row", async () => {
    const user = userEvent.setup()
    stubFetch()
    renderWithProviders(<CannedResponsesConsole />)

    await user.click(within(await rowOf("dot_agency")).getByRole("button", { name: "Edit" }))
    const dialog = await screen.findByRole("dialog")

    expect(
      within(dialog).getByText(`The assistant will not use this wording yet. ${FILL_IN_REASON}`),
    ).toBeInTheDocument()
  })
})
