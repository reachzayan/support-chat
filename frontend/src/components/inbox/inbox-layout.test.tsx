import { screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { InboxConsole } from "./inbox-console"
import {
  ALEX,
  FakeSocket,
  emit,
  emitAlexJoined,
  openQueuedAda,
  resetInboxHarness,
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

  test("renders three panes, Chrome on macOS, and does not link javascript URLs", async () => {
    await openQueuedAda()
    expect(screen.getByRole("navigation", { name: "Inbox filters" })).toBeInTheDocument()
    expect(screen.getByRole("list", { name: "Conversations" })).toBeInTheDocument()
    expect(screen.getByRole("log", { name: "Transcript" })).toBeInTheDocument()
    expect(screen.getByRole("complementary", { name: "Visitor facts" })).toBeInTheDocument()
    expect(screen.getByText("Chrome")).toBeInTheDocument()
    expect(screen.getByText("macOS")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "https://sample-site.example.com/dot" })).toHaveAttribute(
      "rel",
      "noreferrer noopener",
    )
    expect(screen.queryByRole("link", { name: "javascript:alert(1)" })).not.toBeInTheDocument()
    expect(screen.getByText("javascript:alert(1)")).toBeInTheDocument()
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
    expect(within(transcript).getByText("How fast are DOT results?").closest("p")).toHaveClass(
      "rounded-2xl",
      "mr-auto",
      "bg-paper",
    )
    expect(within(transcript).getByText("I can help with that.").closest("p")).toHaveClass(
      "rounded-2xl",
      "ml-auto",
      "bg-navy",
    )
  })
})
