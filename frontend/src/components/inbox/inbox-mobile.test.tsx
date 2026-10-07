import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { InboxConsole } from "./inbox-console"
import { ALEX, CONVO_ID, adaDetail, resetInboxHarness, setDetails } from "./inbox-test-harness"

beforeEach(() => {
  resetInboxHarness()
  vi.stubGlobal("innerWidth", 390)
  vi.stubGlobal("matchMedia", () => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
})
afterEach(() => vi.unstubAllGlobals())

test("visitor details closes back to the same chat and restores its control", async () => {
  const user = userEvent.setup()
  renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
  await screen.findByRole("log", { name: "Transcript" })
  const details = screen.getByRole("button", { name: "Visitor details" })
  await user.click(details)
  expect(await screen.findByRole("dialog", { name: "Visitor details" })).toBeInTheDocument()
  expect(details).toHaveAttribute("aria-expanded", "true")
  await user.keyboard("{Escape}")
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  expect(details).toHaveFocus()
  expect(details).toHaveAttribute("aria-expanded", "false")
  expect(screen.getByRole("log", { name: "Transcript" })).toHaveTextContent(
    "How fast are DOT results?",
  )
})

test.each([320, 390, 820, 1100])(
  "at %i px the inbox opens one pane at a time and returns to its filter",
  async (width) => {
    vi.stubGlobal("innerWidth", width)
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    expect(screen.queryByRole("heading", { name: "Select a conversation" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Needs Attention" }))
    await user.click(await screen.findByRole("button", { name: /Ada Lopez/ }))
    expect(await screen.findByRole("log", { name: "Transcript" })).toBeInTheDocument()
    expect(screen.queryByRole("list", { name: "Conversations" })).not.toBeInTheDocument()
    expect(screen.queryByRole("complementary", { name: "Visitor facts" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Visitor details" }))
    expect(await screen.findByText("ada@example.com")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Close panel" }))
    await user.click(screen.getByRole("button", { name: "Back to conversations" }))
    expect(screen.getByRole("button", { name: /Ada Lopez/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(screen.queryByRole("log", { name: "Transcript" })).not.toBeInTheDocument()
  },
)

test("notification deep link opens its chat even outside the current list filter", async () => {
  renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
  expect(await screen.findByRole("log", { name: "Transcript" })).toHaveTextContent(
    "How fast are DOT results?",
  )
  expect(screen.queryByRole("list", { name: "Conversations" })).not.toBeInTheDocument()
})

test("failed conversation load can be retried or left", async () => {
  setDetails({})
  const user = userEvent.setup()
  renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not open conversation")
  setDetails({ [CONVO_ID]: structuredClone(adaDetail) })
  await user.click(screen.getByRole("button", { name: "Retry" }))
  expect(await screen.findByRole("log", { name: "Transcript" })).toBeInTheDocument()
})

test("leaving a deep-linked conversation clears its URL so its notification can reopen it", async () => {
  window.history.replaceState(null, "", `/admin/inbox?conversation=${CONVO_ID}`)
  const user = userEvent.setup()
  const view = renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
  await screen.findByRole("log", { name: "Transcript" })
  await user.click(screen.getByRole("button", { name: "Back to conversations" }))
  expect(new URLSearchParams(window.location.search).has("conversation")).toBe(false)
  view.rerender(<InboxConsole user={ALEX} initialConversationId={null} />)
  await act(async () =>
    view.rerender(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />),
  )
  expect(await screen.findByRole("log", { name: "Transcript" })).toHaveTextContent(
    "How fast are DOT results?",
  )
})

test("returning to the inbox URL without a conversation restores the list", async () => {
  const view = renderWithProviders(<InboxConsole user={ALEX} initialConversationId={CONVO_ID} />)
  await screen.findByRole("log", { name: "Transcript" })
  view.rerender(<InboxConsole user={ALEX} initialConversationId={null} />)
  expect(await screen.findByRole("list", { name: "Conversations" })).toBeInTheDocument()
  expect(screen.queryByRole("log", { name: "Transcript" })).not.toBeInTheDocument()
})
