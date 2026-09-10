import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test } from "vitest"

import { InboxConsole } from "@/components/inbox/inbox-console"
import { renderWithProviders } from "@/test/render"

import {
  ALEX,
  AGENT_HELP,
  CLIENT_ID,
  CONVO_ID,
  FakeSocket,
  JOIN_LINE,
  JORDAN,
  OTHER_CONVO,
  STILL_THERE,
  adaDetail,
  bgDetail,
  emit,
  emitAlexJoined,
  openQueuedAda,
  resetInboxHarness,
  setDetails,
} from "./inbox-test-harness"

describe("inbox join", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("Join this chat stays pending until committed human state for Alex", async () => {
    const user = await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const socket = FakeSocket.instances[0]
    await user.click(screen.getByRole("button", { name: "Join this chat" }))
    expect(screen.getByRole("button", { name: "Join this chat" })).toHaveAttribute(
      "aria-busy",
      "true",
    )
    expect(screen.getByLabelText("Message")).toBeDisabled()
    emitAlexJoined(socket)
    emit(socket, { v: 1, type: "message", id: 8, role: "system", body: JOIN_LINE })
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Join this chat" })).not.toBeInTheDocument()
    })
    expect(screen.getByLabelText("Message")).toBeEnabled()
    expect(screen.getByRole("button", { name: "End chat" })).toBeEnabled()
    expect(screen.getByText(JOIN_LINE)).toBeInTheDocument()
  })

  test("retries an agent line once and renders the canonical row a single time", async () => {
    const user = await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitAlexJoined(FakeSocket.instances[0])
    await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled())
    await user.type(screen.getByLabelText("Message"), AGENT_HELP)
    await user.click(screen.getByRole("button", { name: "Send" }))
    FakeSocket.instances[0]?.close(1006)
    await waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    emitAlexJoined(FakeSocket.instances[1])
    emit(FakeSocket.instances[1], {
      v: 1,
      type: "message",
      id: 20,
      role: "agent",
      body: AGENT_HELP,
    })
    emit(FakeSocket.instances[1], { v: 1, type: "ack", client_message_id: CLIENT_ID, id: 20 })
    await waitFor(() => expect(screen.getAllByText(AGENT_HELP)).toHaveLength(1))
  })
})

describe("inbox join race", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("loser of Join sees Joined by winner and cannot send", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <div>
        <InboxConsole user={ALEX} />
        <InboxConsole user={JORDAN} />
      </div>,
    )
    const queuedButtons = screen.getAllByRole("button", { name: "Queued" })
    await user.click(queuedButtons[0] as HTMLElement)
    await user.click(queuedButtons[1] as HTMLElement)
    const adaButtons = await screen.findAllByRole("button", { name: /Ada Lopez/ })
    await user.click(adaButtons[0] as HTMLElement)
    await user.click(adaButtons[1] as HTMLElement)
    await waitFor(() => expect(screen.getAllByText("ada@example.com")).toHaveLength(2))
    await waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    const joinButtons = screen.getAllByRole("button", { name: "Join this chat" })
    await user.click(joinButtons[0] as HTMLElement)
    await user.click(joinButtons[1] as HTMLElement)
    emitAlexJoined(FakeSocket.instances[0])
    emit(FakeSocket.instances[0], { v: 1, type: "message", id: 8, role: "system", body: JOIN_LINE })
    emit(FakeSocket.instances[1], {
      v: 1,
      type: "error",
      code: "already_joined",
      display_name: ALEX.display_name,
    })
    emitAlexJoined(FakeSocket.instances[1])
    await waitFor(() => expect(screen.getByText("Joined by Alex Morgan")).toBeInTheDocument())
    const composers = screen.getAllByLabelText("Message")
    expect(composers.filter((node) => !(node as HTMLTextAreaElement).disabled)).toHaveLength(1)
    const before = FakeSocket.instances[1]?.sent.filter((raw) =>
      raw.includes('"type":"message"'),
    ).length
    await user.click(screen.getAllByRole("button", { name: "Send" })[1] as HTMLElement)
    const after = FakeSocket.instances[1]?.sent.filter((raw) =>
      raw.includes('"type":"message"'),
    ).length
    expect(after).toBe(before)
  })
})

describe("inbox after join", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("visitor line after Join stays human and does not add a bot row", async () => {
    await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitAlexJoined(FakeSocket.instances[0])
    emit(FakeSocket.instances[0], { v: 1, type: "message", id: 8, role: "system", body: JOIN_LINE })
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "message",
      id: 9,
      role: "visitor",
      body: STILL_THERE,
    })
    await waitFor(() => expect(screen.getByText(STILL_THERE)).toBeInTheDocument())
    expect(screen.queryByText("bot")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "End chat" })).toBeEnabled()
  })
})

describe("inbox callback leads", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("callback queue shows Mark contacted instead of Join", async () => {
    setDetails({
      [CONVO_ID]: {
        ...adaDetail,
        attention_needed: true,
        human_enabled: false,
      },
      [OTHER_CONVO]: bgDetail,
    })
    await openQueuedAda()
    expect(screen.getByRole("button", { name: "Mark contacted" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Join this chat" })).not.toBeInTheDocument()
    expect(screen.getByText("Needs attention")).toBeInTheDocument()
  })
})

describe("inbox transfer to assistant", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("assigned specialist can transfer a live chat back to the assistant", async () => {
    const user = await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitAlexJoined(FakeSocket.instances[0])
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Transfer to assistant" })).toBeInTheDocument(),
    )
    await user.click(screen.getByRole("button", { name: "Transfer to assistant" }))
    const released = FakeSocket.instances[0]?.sent
      .map((raw) => JSON.parse(raw) as { type?: string; conversation_id?: string })
      .filter((frame) => frame.type === "transfer_to_bot")
    expect(released.at(-1)?.conversation_id).toBe(CONVO_ID)
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "state",
      state: "bot",
      conversation_id: CONVO_ID,
      assigned_agent: null,
    })
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "message",
      id: 12,
      role: "system",
      body: "You're now chatting with the assistant.",
    })
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Join this chat" })).toBeInTheDocument(),
    )
    expect(screen.getByLabelText("Message")).toBeDisabled()
    expect(screen.queryByRole("button", { name: "End chat" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Transfer to assistant" })).not.toBeInTheDocument()
    expect(screen.getByText("You're now chatting with the assistant.")).toBeInTheDocument()
  })

  test("transfer stays hidden when the site bot is off", async () => {
    setDetails({
      [CONVO_ID]: { ...adaDetail, bot_enabled: false },
      [OTHER_CONVO]: bgDetail,
    })
    await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitAlexJoined(FakeSocket.instances[0])
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "End chat" })).toBeInTheDocument(),
    )
    expect(screen.queryByRole("button", { name: "Transfer to assistant" })).not.toBeInTheDocument()
  })
})
