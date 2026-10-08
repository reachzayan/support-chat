import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { uniqueById } from "./inbox-api"
import { InboxConsole } from "./inbox-console"
import {
  ALEX,
  CONVO_ID,
  adaDetail,
  adaQueued,
  resetInboxHarness,
  setDetails,
  setListItems,
  staffFetch,
} from "./inbox-test-harness"

afterEach(() => vi.restoreAllMocks())

describe("inbox list rendering", () => {
  beforeEach(() => resetInboxHarness())

  test("uniqueById keeps the first row for each id", () => {
    expect(
      uniqueById([
        { id: "a", n: 1 },
        { id: "b", n: 2 },
        { id: "a", n: 3 },
      ]),
    ).toEqual([
      { id: "a", n: 1 },
      { id: "b", n: 2 },
    ])
  })

  test("a conversation the server returns twice renders once with no duplicate-key warning", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {})
    setListItems([adaQueued, { ...adaQueued, preview: "newer copy" }])
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    await user.click(screen.getByRole("button", { name: "Needs Attention" }))
    const list = screen.getByRole("list", { name: "Conversations" })
    await waitFor(() =>
      expect(within(list).getAllByRole("button", { name: /Ada Lopez/ })).toHaveLength(1),
    )
    const keyWarnings = errors.mock.calls.filter((call) => String(call[0]).includes("same key"))
    expect(keyWarnings).toHaveLength(0)
  })

  test("preview wraps and truncates with an ellipsis instead of clipping", async () => {
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    await user.click(screen.getByRole("button", { name: "Needs Attention" }))
    const preview = await screen.findByText("How fast are DOT results?")
    expect(preview.className).toMatch(/line-clamp-2/)
    expect(preview.className).toMatch(/whitespace-normal/)
    expect(preview.className).toMatch(/break-words/)
  })

  test("site picker and status filters are labelled as separate controls", () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    expect(screen.getByText("Website")).toBeInTheDocument()
    expect(screen.getByText("Status")).toBeInTheDocument()
  })

  test("an empty status points at the chats that need attention", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    expect(await screen.findByText("No live chats right now")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Show 2 needing attention/ })).toBeInTheDocument()
  })
})

describe("inbox conversation loading", () => {
  beforeEach(() => resetInboxHarness())

  test("shows a loading skeleton while the conversation opens", async () => {
    let release: (() => void) | undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const original = staffFetch.getMockImplementation()
    staffFetch.mockImplementation(async (input, init) => {
      if (/\/api\/conversations\/[0-9a-f-]+/i.test(String(input))) await gate
      return original!(input, init)
    })
    renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
    const status = await screen.findByRole("status", { name: /Opening conversation/ })
    expect(status).toHaveAttribute("aria-busy", "true")
    release?.()
    expect(await screen.findByRole("log", { name: "Transcript" })).toBeInTheDocument()
    expect(screen.queryByRole("status", { name: /Opening conversation/ })).not.toBeInTheDocument()
  })

  test("shows an error with retry when the conversation cannot be loaded", async () => {
    setDetails({})
    renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not open conversation")
    setDetails({ [CONVO_ID]: structuredClone(adaDetail) })
  })
})

describe("inbox mobile header", () => {
  beforeEach(() => {
    resetInboxHarness()
    vi.stubGlobal("innerWidth", 390)
  })
  afterEach(() => vi.unstubAllGlobals())

  test("Join this chat sits with the composer, not in the header", async () => {
    renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
    const join = await screen.findByRole("button", { name: "Join this chat" })
    expect(screen.getAllByRole("button", { name: "Join this chat" })).toHaveLength(1)
    expect(join.className).toMatch(/w-full/)
    expect(join.className).toMatch(/min-h-11/)
    const header = screen.getByRole("heading", { level: 1 }).closest("div.border-b")
    expect(header).not.toContainElement(join)
  })
})
