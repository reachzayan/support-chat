import { afterEach, describe, expect, test, vi } from "vitest"

import { agentSocketUrl, createAgentSocket } from "./agent-ws"

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

type Frame = {
  type: string
  access_token?: string
  conversation_id?: string
  last_event_id?: number
  client_message_id?: string
  body?: string
}

const parsed = (socket: FakeSocket | undefined): Frame[] => {
  return (socket?.sent ?? []).map((raw) => JSON.parse(raw) as Frame)
}

const CONVO = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const CLIENT = "20000000-0000-4000-8000-000000000001"

describe("agent socket client", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  test("production agent socket uses the staff hostname, not the build-time API origin", () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("NEXT_PUBLIC_API_ORIGIN", "http://127.0.0.1:8000")
    vi.stubGlobal("window", { location: { origin: "https://staff.example.test" } })

    expect(agentSocketUrl()).toBe("wss://staff.example.test/ws/agent")
  })

  test("agentSocketUrl treats a blank origin as the local default", () => {
    expect(agentSocketUrl("")).toBe("ws://127.0.0.1:8000/ws/agent")
    expect(agentSocketUrl("   ")).toBe("ws://127.0.0.1:8000/ws/agent")
  })

  test("auths, subscribes from last id, and retries one unacked agent line", async () => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    const socket = createAgentSocket({
      url: "ws://127.0.0.1:8000/ws/agent",
      accessToken: "jwt-alex",
      onFrame: () => undefined,
      onClose: () => undefined,
    })

    await vi.waitFor(() => expect(parsed(FakeSocket.instances[0])[0]?.type).toBe("auth"))
    expect(parsed(FakeSocket.instances[0])[0]?.access_token).toBe("jwt-alex")
    socket.subscribe(CONVO, 12)
    expect(parsed(FakeSocket.instances[0]).find((frame) => frame.type === "subscribe")).toEqual({
      v: 1,
      type: "subscribe",
      conversation_id: CONVO,
      last_event_id: 12,
    })
    socket.sendMessage(CONVO, CLIENT, "I can help with that.")
    FakeSocket.instances[0]?.close(1006)
    socket.reconnect()
    await vi.waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    socket.flushUnacked()
    const messages = parsed(FakeSocket.instances[1]).filter((frame) => frame.type === "message")
    expect(messages).toHaveLength(1)
    expect(messages[0]?.client_message_id).toBe(CLIENT)
    expect(messages[0]?.body).toBe("I can help with that.")
    expect(messages[0]?.conversation_id).toBe(CONVO)
  })
})
