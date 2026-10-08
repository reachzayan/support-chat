import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Profiler, useCallback, useRef } from "react"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { WidgetApp } from "./widget-app"

const PARENT = "http://localhost:3000"
const VISITOR_LINE = "How fast are results?"
const JOIN_LINE = "You're now chatting with Alex Morgan."

class FakeSocket {
  static instances: FakeSocket[] = []
  sent: string[] = []
  readyState = 1
  closeCode: number | null = null
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null

  constructor(public url: string) {
    FakeSocket.instances.push(this)
    queueMicrotask(() => this.onopen?.(new Event("open")))
  }

  send(data: string) {
    this.sent.push(data)
  }

  close(code = 1000) {
    this.closeCode = code
    this.onclose?.({ code } as CloseEvent)
  }
}

const dispatchBootstrap = (conversation?: {
  id?: string
  state: string
  assigned_agent: { id: string; display_name: string } | null
  messages: unknown[]
}) => {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: PARENT,
      source: window.parent,
      data: {
        type: "host.bootstrap",
        bootstrap_token: "boot",
        widget: {
          name: "SupportChat demo",
          greeting: "Talk to a specialist about screening.",
          privacy_url: "http://localhost:3000/privacy",
        },
        page_url: "http://localhost:3000/demo",
        page_title: "Testing LiveChat inhouse",
        referrer: "",
        ...(conversation === undefined ? {} : { conversation }),
      },
    }),
  )
}

const dispatchIdentity = () => {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: PARENT,
      source: window.parent,
      data: {
        type: "host.identity",
        widget: {
          name: "SupportChat demo",
          greeting: "Talk to a specialist about screening.",
          privacy_url: "http://localhost:3000/privacy",
        },
        identity: {
          display_name: "Ada L.",
          email_hint: "a•••@example.com",
          phone_hint: "••• ••• 0198",
          chat_count: 2,
        },
      },
    }),
  )
}

const dispatchHistory = () => {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: PARENT,
      source: window.parent,
      data: {
        type: "host.history",
        widget: {
          name: "SupportChat demo",
          greeting: "Talk to a specialist about screening.",
          privacy_url: "http://localhost:3000/privacy",
        },
        identity: {
          display_name: "Ada L.",
          email_hint: "a•••@example.com",
          phone_hint: null,
          chat_count: 2,
        },
        conversations: [
          {
            id: "10000000-0000-4000-8000-000000000001",
            state: "bot",
            inquiry_type: "results",
            created_at: "2026-09-20T12:00:00Z",
            last_message_at: "2026-09-20T12:10:00Z",
            assigned_agent: null,
            is_current: true,
          },
          {
            id: "10000000-0000-4000-8000-000000000002",
            state: "closed",
            inquiry_type: "compliance",
            created_at: "2026-09-18T12:00:00Z",
            last_message_at: "2026-09-18T12:10:00Z",
            assigned_agent: { id: "agent-1", display_name: "Alex Morgan" },
            is_current: false,
          },
        ],
      },
    }),
  )
}

const emit = (socket: FakeSocket | undefined, payload: unknown) => {
  socket?.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
}

describe("widget first paint", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  test("a prechat snapshot shows the form before any socket state", async () => {
    const postMessage = vi.spyOn(window.parent, "postMessage")
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap({ state: "prechat", assigned_agent: null, messages: [] })

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Start the chat" })).toBeInTheDocument(),
    )
    expect(screen.queryByText("Connecting…")).not.toBeInTheDocument()
    expect(
      postMessage.mock.calls.filter(
        (call) => (call[0] as { type?: string }).type === "widget.painted",
      ).length,
    ).toBe(1)
  })

  test("a resume snapshot shows the prior visitor line before any socket state", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap({
      state: "bot",
      assigned_agent: null,
      messages: [{ type: "message", id: 11, role: "visitor", body: VISITOR_LINE }],
    })

    await waitFor(() => expect(screen.getByText(VISITOR_LINE)).toBeInTheDocument())
    expect(screen.queryByText("Connecting…")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument()
  })

  test("the widget document stays transparent over the host page", () => {
    renderWithProviders(<WidgetApp />)
    expect(document.documentElement.style.backgroundColor).toBe("transparent")
    expect(document.body.style.backgroundColor).toBe("transparent")
  })
})

describe("returning visitor flow", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  test("shows masked identity before requesting any conversation history", async () => {
    const user = userEvent.setup()
    const postMessage = vi.spyOn(window.parent, "postMessage")
    renderWithProviders(<WidgetApp />)
    dispatchIdentity()

    await waitFor(() => expect(screen.getByRole("heading", { name: "Is this you?" })).toBeVisible())
    expect(screen.getByText("Ada L.")).toBeVisible()
    expect(screen.getByText("a•••@example.com")).toBeVisible()
    expect(screen.getByText("••• ••• 0198")).toBeVisible()
    expect(screen.queryByText(VISITOR_LINE)).not.toBeInTheDocument()
    expect(FakeSocket.instances).toHaveLength(0)

    await user.click(screen.getByRole("button", { name: "Yes, show my chats" }))
    expect(postMessage).toHaveBeenCalledWith({ type: "widget.show_history" }, PARENT)
  })

  test("lists compact chat metadata and confirms replacing an active chat", async () => {
    const user = userEvent.setup()
    const postMessage = vi.spyOn(window.parent, "postMessage")
    renderWithProviders(<WidgetApp />)
    dispatchHistory()

    await waitFor(() => expect(screen.getByRole("heading", { name: "Your chats" })).toBeVisible())
    expect(screen.getByRole("button", { name: /Results question.*Current chat/i })).toBeVisible()
    expect(screen.getByRole("button", { name: /Compliance question.*Past chat/i })).toBeVisible()
    expect(screen.queryByText(VISITOR_LINE)).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /Compliance question.*Past chat/i }))
    await user.click(screen.getByRole("button", { name: "Resume chat" }))
    expect(screen.getByRole("dialog", { name: "Resume this chat instead?" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Resume chat" }))
    expect(postMessage).toHaveBeenCalledWith(
      {
        type: "widget.open_conversation",
        conversation_id: "10000000-0000-4000-8000-000000000002",
        replace_current: true,
      },
      PARENT,
    )
  })
})

describe("widget bootstrap race", () => {
  test("registers the host listener before posting widget.ready", () => {
    Object.defineProperty(document, "referrer", { value: `${PARENT}/demo`, configurable: true })
    const order: string[] = []
    const addListener = window.addEventListener.bind(window)
    const postMessage = window.parent.postMessage.bind(window.parent)
    vi.spyOn(window, "addEventListener").mockImplementation((type, listener, options) => {
      if (type === "message") {
        order.push("listener")
      }
      addListener(type, listener, options)
    })
    vi.spyOn(window.parent, "postMessage").mockImplementation((payload, targetOrigin) => {
      if ((payload as { type?: string }).type === "widget.ready") {
        order.push("ready")
      }
      postMessage(payload, targetOrigin)
    })

    renderWithProviders(<WidgetApp />)

    expect(order.indexOf("listener")).toBeGreaterThanOrEqual(0)
    expect(order.indexOf("ready")).toBeGreaterThan(order.indexOf("listener"))
    vi.restoreAllMocks()
  })
})

describe("widget panel resume", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  test("open human conversation skips pre-chat and shows prior lines", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const socket = FakeSocket.instances[0]
    emit(socket, { v: 1, type: "message", id: 1, role: "visitor", body: VISITOR_LINE })
    emit(socket, { v: 1, type: "message", id: 2, role: "system", body: JOIN_LINE })
    emit(socket, {
      v: 1,
      type: "state",
      state: "human",
      assigned_agent: { id: "agent-1", display_name: "Alex Morgan" },
    })

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: "SupportChat" })).toBeInTheDocument()
    })
    expect(screen.queryByRole("button", { name: "Start the chat" })).not.toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(VISITOR_LINE)).toBeInTheDocument()
      expect(screen.getByText(JOIN_LINE)).toBeInTheDocument()
    })
    expect(screen.queryByRole("button", { name: "Talk to a person" })).not.toBeInTheDocument()
    expect(screen.getByRole("dialog", { name: "SupportChat" })).toBeInTheDocument()
  })

  test("invalid email keeps pre-chat visible and sends no prechat frame", async () => {
    const user = userEvent.setup()
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const socket = FakeSocket.instances[0]
    emit(socket, { v: 1, type: "state", state: "prechat", assigned_agent: null })
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Start the chat" })).toBeInTheDocument(),
    )
    const sentBefore = [...(socket?.sent ?? [])]

    await user.type(screen.getByLabelText("Full name"), "Ada Lopez")
    await user.type(screen.getByLabelText("Email"), "not-an-email")
    await user.click(screen.getByRole("button", { name: "Start the chat" }))

    expect(screen.getByRole("button", { name: "Start the chat" })).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toHaveFocus()
    expect(socket?.sent).toEqual(sentBefore)
    expect(sentBefore.some((raw) => raw.includes('"type":"prechat"'))).toBe(false)
  })

  test("a new prechat conversation does not keep prior canonical lines in bot", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const socket = FakeSocket.instances[0]
    emit(socket, { v: 1, type: "message", id: 1, role: "visitor", body: VISITOR_LINE })
    emit(socket, {
      v: 1,
      type: "state",
      state: "human",
      assigned_agent: { id: "agent-1", display_name: "Alex Morgan" },
    })
    await waitFor(() => expect(screen.getByText("A human has joined")).toBeInTheDocument())
    emit(socket, { v: 1, type: "state", state: "prechat", assigned_agent: null })
    emit(socket, { v: 1, type: "state", state: "bot", assigned_agent: null })

    await waitFor(() =>
      expect(screen.queryByText("Chatting with Alex Morgan")).not.toBeInTheDocument(),
    )
    expect(screen.queryByText(VISITOR_LINE)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument()
  })
})

describe("widget send and reconnect", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  test("send error keeps Send disabled until the visitor writes another message", async () => {
    const user = userEvent.setup()
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const socket = FakeSocket.instances[0]
    emit(socket, { v: 1, type: "state", state: "bot", assigned_agent: null })
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeDisabled())
    await user.type(screen.getByLabelText("Message"), VISITOR_LINE)
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled()
    await user.click(screen.getByRole("button", { name: "Send" }))
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled()
    emit(socket, { v: 1, type: "error", code: "invalid" })
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeDisabled())
  })

  test("expand control asks the host for a bounded panel height", async () => {
    const user = userEvent.setup()
    const postMessage = vi.spyOn(window.parent, "postMessage")
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Expand chat" })).toBeInTheDocument(),
    )
    postMessage.mockClear()

    await user.click(screen.getByRole("button", { name: "Expand chat" }))

    expect(postMessage).toHaveBeenCalledWith(
      { type: "widget.resize", height: 720, width: 500 },
      PARENT,
    )
  })
})

describe("widget reconnect backoff", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  test("socket close storms backoff reconnect instead of opening immediately", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      renderWithProviders(<WidgetApp />)
      dispatchBootstrap()
      await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
      const first = FakeSocket.instances[0]
      first?.close(1006)
      first?.close(1006)
      first?.close(1006)
      expect(FakeSocket.instances.length).toBe(1)
      await vi.advanceTimersByTimeAsync(30_000)
      expect(FakeSocket.instances.length).toBe(2)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("widget lifecycle", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  test("origin close 4403 does not open another visitor socket", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    FakeSocket.instances[0]?.close(4403)
    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(FakeSocket.instances.length).toBe(1)
  })

  test("closed chats show the lifecycle notice in the transcript and keep a restart path", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emit(FakeSocket.instances[0], { v: 1, type: "state", state: "closed", assigned_agent: null })

    await waitFor(() => expect(screen.getByText("This chat is closed")).toBeInTheDocument())
    expect(
      screen.getByText("This chat is closed").closest("[data-slot='marker-content']"),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Start a new chat" })).toBeInTheDocument()
  })

  test("stale bootstrap does not replace a closed transcript", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap({
      id: "10000000-0000-4000-8000-000000000011",
      state: "bot",
      assigned_agent: null,
      messages: [{ type: "message", id: 11, role: "visitor", body: VISITOR_LINE }],
    })
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "state",
      state: "closed",
      conversation_id: "10000000-0000-4000-8000-000000000011",
      assigned_agent: null,
    })
    await waitFor(() => expect(screen.getByText("This chat is closed")).toBeInTheDocument())

    dispatchBootstrap({
      id: "10000000-0000-4000-8000-000000000011",
      state: "bot",
      assigned_agent: null,
      messages: [{ type: "message", id: 11, role: "visitor", body: VISITOR_LINE }],
    })

    expect(screen.getByText("This chat is closed")).toBeInTheDocument()
    expect(screen.getByText(VISITOR_LINE)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Start a new chat" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Start the chat" })).not.toBeInTheDocument()
  })

  test("returning identity bootstrap does not replace a closed transcript", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap({
      id: "10000000-0000-4000-8000-000000000011",
      state: "bot",
      assigned_agent: null,
      messages: [{ type: "message", id: 11, role: "visitor", body: VISITOR_LINE }],
    })
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "state",
      state: "closed",
      conversation_id: "10000000-0000-4000-8000-000000000011",
      assigned_agent: null,
    })
    await waitFor(() => expect(screen.getByText("This chat is closed")).toBeInTheDocument())

    dispatchIdentity()

    expect(screen.getByText("This chat is closed")).toBeInTheDocument()
    expect(screen.queryByText("Is this you?")).not.toBeInTheDocument()
  })
})

describe("widget socket resume", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  test("regaining tab focus does not open a second visitor socket", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    Object.defineProperty(document, "hidden", { configurable: true, value: false })
    document.dispatchEvent(new Event("visibilitychange"))
    await new Promise((resolve) => setTimeout(resolve, 600))
    expect(FakeSocket.instances.length).toBe(1)
  })

  test("leaving the widget closes the visitor socket", async () => {
    const view = renderWithProviders(<WidgetApp />)
    dispatchBootstrap()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const first = FakeSocket.instances[0]
    view.unmount()
    expect(first?.closeCode).toBe(1000)
  })
})

describe("widget human routing", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("fetch", vi.fn())
  })

  test("hides talk to a person when human is off", async () => {
    renderWithProviders(<WidgetApp />)
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: PARENT,
        source: window.parent,
        data: {
          type: "host.bootstrap",
          bootstrap_token: "boot",
          widget: {
            name: "SupportChat demo",
            greeting: "Talk to a specialist about screening.",
            privacy_url: "http://localhost:3000/privacy",
            bot_enabled: true,
            human_enabled: false,
          },
          page_url: "http://localhost:3000/demo",
          page_title: "Testing LiveChat inhouse",
          referrer: "",
        },
      }),
    )
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emit(FakeSocket.instances[0], { v: 1, type: "state", state: "bot", assigned_agent: null })
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument())
    expect(screen.queryByRole("button", { name: "Talk to a person" })).not.toBeInTheDocument()
  })

  test("queued callback with humans off closes the visitor chat and keeps a restart path", async () => {
    renderWithProviders(<WidgetApp />)
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: PARENT,
        source: window.parent,
        data: {
          type: "host.bootstrap",
          bootstrap_token: "boot",
          widget: {
            name: "SupportChat demo",
            greeting: "Talk to a specialist about screening.",
            privacy_url: "http://localhost:3000/privacy",
            bot_enabled: true,
            human_enabled: false,
          },
          page_url: "http://localhost:3000/demo",
          page_title: "Testing LiveChat inhouse",
          referrer: "",
        },
      }),
    )
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "message",
      id: 1,
      role: "system",
      body: "A representative will contact you in 24 hours.",
    })
    emit(FakeSocket.instances[0], { v: 1, type: "state", state: "queued", assigned_agent: null })
    await waitFor(() =>
      expect(
        screen.getByText("A representative will contact you in 24 hours."),
      ).toBeInTheDocument(),
    )
    expect(screen.getByText("This chat is closed")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Start a new chat" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Talk to a person" })).not.toBeInTheDocument()
  })
})

test("only fresh bot and agent replies notify the host; snapshots, history and duplicates stay silent", async () => {
  FakeSocket.instances = []
  vi.stubGlobal("WebSocket", FakeSocket)
  const posted = vi.spyOn(window.parent, "postMessage")
  const chatId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
  renderWithProviders(<WidgetApp />)
  dispatchBootstrap({
    id: chatId,
    state: "bot",
    assigned_agent: null,
    messages: [{ type: "message", id: 10, role: "bot", body: "Old reply" }],
  })
  await screen.findByText("Old reply")
  const socket = FakeSocket.instances[0]
  emit(socket, { type: "message", id: 11, role: "visitor", body: "My message" })
  await screen.findByText("My message")
  emit(socket, {
    type: "history_page",
    has_older: false,
    messages: [{ type: "message", id: 8, role: "agent", body: "Historical reply" }],
  })
  await screen.findByText("Historical reply")
  emit(socket, { type: "message", id: 12, role: "bot", body: "New bot reply" })
  await screen.findByText("New bot reply")
  emit(socket, { type: "message", id: 12, role: "bot", body: "New bot reply" })
  emit(socket, { type: "message", id: 13, role: "agent", body: "New agent reply" })
  await screen.findByText("New agent reply")
  expect(
    posted.mock.calls.filter(([frame]) => frame.type === "widget.message").map(([frame]) => frame),
  ).toEqual([
    { type: "widget.message", conversation_id: chatId, message_id: 12 },
    { type: "widget.message", conversation_id: chatId, message_id: 13 },
  ])
  posted.mockRestore()
})

test("handoff and busy messages appear in the transcript and announce new widget activity", async () => {
  FakeSocket.instances = []
  vi.stubGlobal("WebSocket", FakeSocket)
  const posted = vi.spyOn(window.parent, "postMessage")
  const chatId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
  renderWithProviders(<WidgetApp />)
  dispatchBootstrap({
    id: chatId,
    state: "bot",
    assigned_agent: null,
    messages: [{ type: "message", id: 10, role: "visitor", body: "I need a person" }],
  })
  await screen.findByText("I need a person")
  const socket = FakeSocket.instances[0]
  emit(socket, {
    type: "message",
    id: 11,
    role: "system",
    system_reason: "visitor_request",
    body: "A specialist will join this chat shortly.",
  })
  emit(socket, { type: "state", state: "queued", assigned_agent: null })
  emit(socket, {
    type: "message",
    id: 12,
    role: "system",
    body: "Our agents are all currently busy right now. Would you like to wait?",
  })
  emit(socket, { type: "state", state: "queued", assigned_agent: null, handoff_wait_prompt_id: 12 })
  const transcript = await screen.findByRole("log")
  expect(transcript).toHaveTextContent("A specialist will join this chat shortly.")
  expect(transcript).toHaveTextContent(
    "Our agents are all currently busy right now. Would you like to wait?",
  )
  expect(await screen.findByRole("button", { name: "Keep waiting" })).toBeEnabled()
  emit(socket, {
    type: "message",
    id: 12,
    role: "system",
    body: "Our agents are all currently busy right now. Would you like to wait?",
  })
  emit(socket, {
    type: "message",
    id: 13,
    role: "system",
    body: "You're now chatting with Alex Morgan.",
  })
  expect(
    posted.mock.calls.filter(([frame]) => frame.type === "widget.message").map(([frame]) => frame),
  ).toEqual([
    { type: "widget.message", conversation_id: chatId, message_id: 11 },
    { type: "widget.message", conversation_id: chatId, message_id: 12 },
  ])
})

// Inject frames at commit boundaries to reproduce an older render racing newer socket state.
const HandoffCommitRace = () => {
  const delivered = useRef(false)
  const repeatedState = useRef(false)
  const onRender = useCallback(() => {
    const hasHandoff = screen
      .queryByRole("log")
      ?.textContent?.includes("A specialist will join this chat shortly.")
    if (delivered.current && !repeatedState.current && hasHandoff) {
      repeatedState.current = true
      emit(FakeSocket.instances[0], { type: "state", state: "queued", assigned_agent: null })
      return
    }
    if (delivered.current || !screen.queryByText("I want to talk to a human")) return
    delivered.current = true
    emit(FakeSocket.instances[0], {
      type: "message",
      id: 12,
      role: "system",
      system_reason: "visitor_request",
      body: "A specialist will join this chat shortly.",
    })
    emit(FakeSocket.instances[0], { type: "state", state: "queued", assigned_agent: null })
  }, [])
  return (
    <Profiler id="visitor-chat" onRender={onRender}>
      <WidgetApp />
    </Profiler>
  )
}

test("a handoff arriving during a visitor-message commit survives the following state frame", async () => {
  FakeSocket.instances = []
  vi.stubGlobal("WebSocket", FakeSocket)
  renderWithProviders(<HandoffCommitRace />)
  dispatchBootstrap({
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    state: "bot",
    assigned_agent: null,
    messages: [{ type: "message", id: 10, role: "system", body: "Welcome" }],
  })
  await screen.findByText("Welcome")
  emit(FakeSocket.instances[0], {
    type: "message",
    id: 11,
    role: "visitor",
    body: "I want to talk to a human",
  })
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument(),
  )
  expect(screen.getByRole("log")).toHaveTextContent("A specialist will join this chat shortly.")
})

test.each([
  ["Keep waiting", "wait"],
  ["End chat", "end"],
])("handoff offers %s using the current server prompt", async (label, choice) => {
  FakeSocket.instances = []
  vi.stubGlobal("WebSocket", FakeSocket)
  const user = userEvent.setup()
  renderWithProviders(<WidgetApp />)
  dispatchBootstrap({
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    state: "queued",
    assigned_agent: null,
    messages: [
      {
        type: "message",
        id: 10,
        role: "system",
        body: "A specialist will join this chat shortly.",
      },
    ],
  })
  await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
  const socket = FakeSocket.instances[0]
  emit(socket, {
    type: "message",
    id: 11,
    role: "system",
    body: "Our agents are all currently busy right now. Would you like to wait?",
  })
  emit(socket, { type: "state", state: "queued", assigned_agent: null, handoff_wait_prompt_id: 11 })
  await user.click(await screen.findByRole("button", { name: label }))
  expect(
    socket.sent
      .map((raw) => JSON.parse(raw))
      .filter((frame) => frame.type === "handoff_wait_response"),
  ).toEqual([{ v: 1, type: "handoff_wait_response", prompt_id: 11, choice }])
  emit(socket, {
    type: "state",
    state: "human",
    assigned_agent: { id: "alex", display_name: "Alex" },
    handoff_wait_prompt_id: null,
  })
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "Keep waiting" })).not.toBeInTheDocument(),
  )
  expect(screen.queryByRole("button", { name: "End chat" })).not.toBeInTheDocument()
})
