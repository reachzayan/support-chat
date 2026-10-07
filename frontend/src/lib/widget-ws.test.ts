import { afterEach, describe, expect, test, vi } from "vitest"

import { createVisitorSocket, visitorSocketUrl } from "./widget-ws"

class FakeSocket {
  static instances: FakeSocket[] = []
  sent: string[] = []
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  readyState = 1

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

type Frame = { type: string; last_event_id?: number; client_message_id?: string }

const parsed = (socket: FakeSocket | undefined): Frame[] => {
  return (socket?.sent ?? []).map((raw) => JSON.parse(raw) as Frame)
}

const emitMessage = (socket: FakeSocket | undefined, id: number, body: string) => {
  socket?.onmessage?.({
    data: JSON.stringify({ v: 1, type: "message", id, role: "visitor", body }),
  } as MessageEvent)
}

describe("visitor socket client", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  test("production visitor socket uses the widget hostname, not the build-time API origin", () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("NEXT_PUBLIC_API_ORIGIN", "http://127.0.0.1:8000")
    vi.stubGlobal("window", { location: { origin: "https://widget.example.test" } })

    expect(visitorSocketUrl()).toBe("wss://widget.example.test/ws/visitor")
  })

  test("reconnects after cursor 12 and retries one unacked client id once", async () => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    const socket = createVisitorSocket({
      url: "ws://127.0.0.1:8000/ws/visitor",
      bootstrapToken: "boot",
      parentOrigin: "http://host.localhost:3000",
      onFrame: () => undefined,
      onClose: () => undefined,
    })

    await vi.waitFor(() => expect(FakeSocket.instances[0]?.sent.length).toBeGreaterThan(0))
    const first = FakeSocket.instances[0]
    emitMessage(first, 11, "first")
    emitMessage(first, 12, "second")
    socket.sendMessage("10000000-0000-4000-8000-000000000099", "still there?")
    first?.close(1006)
    socket.reconnect()

    await vi.waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    const second = parsed(FakeSocket.instances[1])
    expect(second.some((frame) => frame.type === "auth")).toBe(true)
    socket.resume(12)
    expect(
      parsed(FakeSocket.instances[1]).find((frame) => frame.type === "resume")?.last_event_id,
    ).toBe(12)
    socket.flushUnacked()
    const messages = parsed(FakeSocket.instances[1]).filter((frame) => frame.type === "message")
    expect(messages).toHaveLength(1)
    expect(messages[0]?.client_message_id).toBe("10000000-0000-4000-8000-000000000099")
  })

  test("a wait choice survives reconnect until acknowledged, then stops retrying", async () => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    const socket = createVisitorSocket({
      url: "ws://127.0.0.1:8000/ws/visitor",
      bootstrapToken: "boot",
      parentOrigin: "http://host.localhost:3000",
      onFrame: () => undefined,
      onClose: () => undefined,
    })
    await vi.waitFor(() => expect(FakeSocket.instances[0]?.sent.length).toBeGreaterThan(0))
    socket.respondHandoffWait(42, "wait")
    socket.reconnect()
    await vi.waitFor(() => expect(FakeSocket.instances[1]?.sent.length).toBeGreaterThan(0))
    expect(
      parsed(FakeSocket.instances[1]).filter((frame) => frame.type === "handoff_wait_response"),
    ).toEqual([{ v: 1, type: "handoff_wait_response", prompt_id: 42, choice: "wait" }])
    FakeSocket.instances[1]?.onmessage?.({
      data: JSON.stringify({ type: "handoff_wait_accepted" }),
    } as MessageEvent)
    socket.reconnect()
    await vi.waitFor(() => expect(FakeSocket.instances[2]?.sent.length).toBeGreaterThan(0))
    expect(
      parsed(FakeSocket.instances[2]).filter((frame) => frame.type === "handoff_wait_response"),
    ).toEqual([])
  })
})
