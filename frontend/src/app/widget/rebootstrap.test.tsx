import { screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { WidgetApp } from "./widget-app"

const PARENT = "http://localhost:3000"

class FakeSocket {
  static instances: FakeSocket[] = []
  sent: string[] = []
  readyState = 1
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
    this.onclose?.({ code } as CloseEvent)
  }
}

const dispatchBootstrap = (
  token: string,
  conversation?: {
    id?: string
    state: string
    assigned_agent: null
    messages: unknown[]
  },
) => {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: PARENT,
      source: window.parent,
      data: {
        type: "host.bootstrap",
        bootstrap_token: token,
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

const emitJson = (socket: FakeSocket | undefined, payload: unknown) => {
  socket?.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
}

const sentFrames = (socket: FakeSocket | undefined) => {
  return (socket?.sent ?? []).map(
    (raw) => JSON.parse(raw) as { type: string; last_event_id?: number; bootstrap_token?: string },
  )
}

/* oxlint-disable max-lines-per-function -- shared socket harness for rebootstrap cases */
describe("widget socket expiry", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  test("4401 rebootstrap posts refresh with the current conversation id", async () => {
    const posted: unknown[] = []
    vi.spyOn(window.parent, "postMessage").mockImplementation((data, origin) => {
      posted.push({ data, origin })
    })

    renderWithProviders(<WidgetApp />)
    dispatchBootstrap("boot", {
      id: "10000000-0000-4000-8000-000000000011",
      state: "bot",
      assigned_agent: null,
      messages: [{ type: "message", id: 11, role: "visitor", body: "How fast are results?" }],
    })
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitJson(FakeSocket.instances[0], {
      v: 1,
      type: "state",
      state: "closed",
      conversation_id: "10000000-0000-4000-8000-000000000011",
      assigned_agent: null,
    })
    FakeSocket.instances[0]?.close(4401)

    await waitFor(() => {
      const rebootstraps = posted.filter(
        (frame) => (frame as { data: { type: string } }).data?.type === "widget.rebootstrap",
      )
      expect(rebootstraps).toHaveLength(1)
      expect(
        (rebootstraps[0] as { data: { conversation_id?: string } }).data?.conversation_id,
      ).toBe("10000000-0000-4000-8000-000000000011")
    })
  })

  test("close 4401 asks the host to rebootstrap once", async () => {
    const posted: unknown[] = []
    vi.spyOn(window.parent, "postMessage").mockImplementation((data, origin) => {
      posted.push({ data, origin })
    })

    renderWithProviders(<WidgetApp />)
    dispatchBootstrap("boot")
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    FakeSocket.instances[0]?.close(4401)

    await waitFor(() => {
      const rebootstraps = posted.filter(
        (frame) => (frame as { data: { type: string } }).data?.type === "widget.rebootstrap",
      )
      expect(rebootstraps).toHaveLength(1)
      expect((rebootstraps[0] as { origin: string }).origin).toBe(PARENT)
    })
  })

  test("4401 then host.bootstrap resumes after canonical id 12", async () => {
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap("boot-1")
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    const first = FakeSocket.instances[0]
    emitJson(first, {
      v: 1,
      type: "message",
      id: 11,
      role: "visitor",
      body: "How fast are results?",
    })
    emitJson(first, { v: 1, type: "message", id: 12, role: "visitor", body: "still there?" })
    emitJson(first, { v: 1, type: "state", state: "bot", assigned_agent: null })
    await waitFor(() => expect(document.body.textContent).toContain("still there?"))
    first?.close(4401)

    dispatchBootstrap("boot-2")
    await waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    await waitFor(() => {
      const frames = sentFrames(FakeSocket.instances[1])
      expect(frames.find((frame) => frame.type === "auth")?.bootstrap_token).toBe("boot-2")
      expect(frames.find((frame) => frame.type === "auth")?.last_event_id).toBe(12)
    })
  })

  test("an older bootstrap cannot erase live handoff messages or waiting choices", async () => {
    const snapshot = {
      id: "10000000-0000-4000-8000-000000000011",
      state: "bot",
      assigned_agent: null,
      messages: [{ type: "message", id: 11, role: "visitor", body: "I need a person" }],
    }
    renderWithProviders(<WidgetApp />)
    dispatchBootstrap("boot-1", snapshot)
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitJson(FakeSocket.instances[0], {
      type: "message",
      id: 12,
      role: "system",
      system_reason: "visitor_request",
      body: "A specialist will join this chat shortly.",
    })
    emitJson(FakeSocket.instances[0], { type: "state", state: "queued", assigned_agent: null })
    await waitFor(() =>
      expect(screen.getByRole("log")).toHaveTextContent(
        "A specialist will join this chat shortly.",
      ),
    )
    emitJson(FakeSocket.instances[0], {
      type: "message",
      id: 13,
      role: "system",
      body: "Our agents are all currently busy right now. Would you like to wait?",
    })
    emitJson(FakeSocket.instances[0], {
      type: "state",
      state: "queued",
      assigned_agent: null,
      handoff_wait_prompt_id: 13,
    })
    await screen.findByRole("button", { name: "Keep waiting" })
    dispatchBootstrap("boot-2", snapshot)
    await waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    expect(screen.getByRole("log")).toHaveTextContent("A specialist will join this chat shortly.")
    expect(screen.getByRole("log")).toHaveTextContent(
      "Our agents are all currently busy right now. Would you like to wait?",
    )
    expect(screen.getByRole("button", { name: "Keep waiting" })).toBeEnabled()
    expect(screen.queryByRole("textbox", { name: "Message" })).not.toBeInTheDocument()
  })
})
