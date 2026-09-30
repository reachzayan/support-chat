import { screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { InboxConsole } from "./inbox-console"
import {
  ALEX,
  CONVO_ID,
  FakeSocket,
  adaDetail,
  emit,
  emitAlexJoined,
  openQueuedAda,
  resetInboxHarness,
  setDetails,
  setListItems,
  setOlderDetails,
} from "./inbox-test-harness"

describe("inbox layout", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("empty pane asks to select a conversation and hides the composer", () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    expect(screen.getByRole("heading", { name: "Select a conversation" })).toBeInTheDocument()
    expect(screen.queryByLabelText("Message")).not.toBeInTheDocument()
    expect(screen.queryByRole("log", { name: "Transcript" })).not.toBeInTheDocument()
  })

  test("empty conversation list omits the decorative placeholder", async () => {
    setListItems([])
    renderWithProviders(<InboxConsole user={ALEX} />)

    const conversations = screen.getByRole("list", { name: "Conversations" })
    await waitFor(() => expect(within(conversations).getByText("Inbox clear")).toBeInTheDocument())
    expect(within(conversations).getByText("Inbox clear").parentElement).not.toContainHTML(
      "rounded-full",
    )
  })

  test("renders three panes, Chrome on macOS, and does not link javascript URLs", async () => {
    await openQueuedAda()
    expect(screen.getByRole("navigation", { name: "Inbox filters" })).toBeInTheDocument()
    expect(screen.getByRole("navigation", { name: "Inbox filters" }).className).toMatch(
      /rounded-full/,
    )
    expect(screen.getByRole("navigation", { name: "Inbox filters" }).className).toMatch(/\bw-fit\b/)
    expect(screen.getByRole("navigation", { name: "Inbox filters" }).className).toMatch(
      /flex-nowrap/,
    )
    expect(screen.getByRole("navigation", { name: "Inbox filters" }).className).not.toMatch(
      /overflow-visible/,
    )
    expect(
      screen.getByRole("heading", { name: "Conversations" }).closest("section")?.className,
    ).toMatch(/overflow-hidden/)
    expect(screen.getByRole("heading", { name: "Conversations" }).closest("section")).toHaveStyle({
      width: "360px",
    })
    const needsAttention = screen.getByRole("button", { name: "Needs Attention" })
    expect(needsAttention).toHaveTextContent(/^Needs Attention 2$/)
    expect(needsAttention.className).not.toMatch(/\btruncate\b/)
    expect(needsAttention.querySelector(".truncate")).toBeNull()
    expect(screen.getByRole("button", { name: "Closed" })).toHaveTextContent(/^Closed 0$/)
    expect(screen.getByRole("button", { name: "Live" })).toHaveTextContent(/^Live 0$/)
    expect(screen.getByRole("button", { name: "Bot" })).toHaveTextContent(/^Bot 0$/)
    expect(screen.queryByLabelText(/^\d+ conversations$/)).not.toBeInTheDocument()
    const transcriptHeader = screen.getByRole("heading", { level: 1 }).closest("div.border-b")
    const visitorHeader = screen
      .getByRole("complementary", { name: "Visitor facts" })
      .querySelector(".border-b")
    expect(transcriptHeader?.className).toMatch(/\bh-16\b/)
    expect(visitorHeader?.className).toMatch(/\bh-16\b/)
    expect(
      screen.getByRole("heading", { name: "Conversations" }).closest("div")?.className,
    ).toMatch(/\bh-16\b/)
    expect(screen.getByRole("list", { name: "Conversations" })).toBeInTheDocument()
    expect(screen.getByRole("log", { name: "Transcript" })).toBeInTheDocument()
    expect(screen.getByRole("complementary", { name: "Visitor facts" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Block visitor" })).toBeInTheDocument()
    expect(screen.getByText("Chrome")).toBeInTheDocument()
    expect(screen.getByText("macOS")).toBeInTheDocument()
    expect(screen.getByText("New York, New York, United States")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "https://sample-site.example.com/dot" })).toHaveAttribute(
      "rel",
      "noreferrer noopener",
    )
    expect(screen.queryByRole("link", { name: "javascript:alert(1)" })).not.toBeInTheDocument()
    expect(screen.getByText("javascript:alert(1)")).toBeInTheDocument()
  })
})

describe("inbox transcript bubbles", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("admin transcript uses the same bubble shapes as the visitor widget", async () => {
    await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitAlexJoined(FakeSocket.instances[0])
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "message",
      id: 20,
      role: "agent",
      body: "I can help with that.",
    })
    await waitFor(() => expect(screen.getByText("I can help with that.")).toBeInTheDocument())
    const transcript = screen.getByRole("log", { name: "Transcript" })
    expect(within(transcript).queryByRole("img")).not.toBeInTheDocument()
    expect(
      within(transcript).getByText("How fast are DOT results?").closest('[data-slot="message"]'),
    ).toHaveAttribute("data-align", "start")
    expect(
      within(transcript).getByText("I can help with that.").closest('[data-slot="message"]'),
    ).toHaveAttribute("data-align", "end")
  })
})

describe("inbox visitor block", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("a blocked visitor shows Unblock instead of Block", async () => {
    setDetails({
      [CONVO_ID]: { ...structuredClone(adaDetail), blocked: true, block_id: "block-1" },
    })
    await openQueuedAda()
    expect(screen.getByRole("button", { name: "Unblock visitor" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Block visitor" })).not.toBeInTheDocument()
  })

  test("blocking from the rail switches the action to Unblock", async () => {
    const user = await openQueuedAda()
    await user.click(screen.getByRole("button", { name: "Block visitor" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Block visitor" }))
    await waitFor(() => expect(screen.getByText("Visitor blocked.")).toBeInTheDocument())
    expect(screen.getByRole("button", { name: "Unblock visitor" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Block visitor" })).not.toBeInTheDocument()
  })

  test("a closed chat shows the closed pill in the transcript", async () => {
    setDetails({
      [CONVO_ID]: { ...structuredClone(adaDetail), state: "closed" },
    })
    await openQueuedAda()
    const transcript = screen.getByRole("log", { name: "Transcript" })
    expect(
      within(transcript).getByText("This chat is closed").closest("[data-slot='marker-content']"),
    ).not.toBeNull()
    expect(within(transcript).queryByText("This chat was closed.")).not.toBeInTheDocument()
  })
})

describe("inbox transcript pagination", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("loads older transcript messages only when requested", async () => {
    setDetails({
      ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]: {
        ...structuredClone(adaDetail),
        messages: [
          {
            ...adaDetail.messages[0],
            id: 501,
            body: "Newest answer",
          },
        ],
        has_older: true,
        older_before_id: 501,
      },
    })
    setOlderDetails({
      ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa:501"]: {
        ...structuredClone(adaDetail),
        messages: [
          {
            ...adaDetail.messages[0],
            id: 1,
            body: "Oldest question",
          },
        ],
        has_older: false,
        older_before_id: null,
      },
    })

    const user = await openQueuedAda()
    await waitFor(() => expect(screen.getByText("Newest answer")).toBeInTheDocument())
    expect(screen.queryByText("Oldest question")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Load older messages" }))

    await waitFor(() => expect(screen.getByText("Oldest question")).toBeInTheDocument())
    expect(screen.queryByRole("button", { name: "Load older messages" })).not.toBeInTheDocument()
  })
})
