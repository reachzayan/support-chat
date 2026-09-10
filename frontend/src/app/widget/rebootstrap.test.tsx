import { waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, test, vi } from "vitest"

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

const dispatchBootstrap = (token: string) => {
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

describe("widget socket expiry", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
  })

  test("close 4401 asks the host to rebootstrap once", async () => {
    const posted: unknown[] = []
    const original = window.parent.postMessage.bind(window.parent)
    vi.spyOn(window.parent, "postMessage").mockImplementation((data, origin) => {
      posted.push({ data, origin })
      original(data, origin as string)
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
      expect(frames.find((frame) => frame.type === "resume")?.last_event_id).toBe(12)
    })
  })
})
