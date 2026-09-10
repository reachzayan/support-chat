import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { WidgetApp } from "./widget-app"

const PARENT = "http://localhost:3000"
const CLIENT_ID = "10000000-0000-4000-8000-000000000099"
const BODY = "still there?"

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

const boot = async () => {
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
          greeting: "Hi",
          privacy_url: "http://localhost:3000/privacy",
        },
        page_url: "http://localhost:3000/demo",
        page_title: "Testing LiveChat inhouse",
        referrer: "",
      },
    }),
  )
  await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
}

describe("canonical visitor rows", () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.stubGlobal("WebSocket", FakeSocket)
    vi.stubGlobal("crypto", { ...crypto, randomUUID: () => CLIENT_ID })
  })

  test("retried unacked client id renders the canonical row once", async () => {
    const user = userEvent.setup()
    await boot()
    const first = FakeSocket.instances[0]
    first?.onmessage?.({
      data: JSON.stringify({ v: 1, type: "state", state: "bot", assigned_agent: null }),
    } as MessageEvent)
    await waitFor(() => expect(screen.getByLabelText("Message")).toBeInTheDocument())
    await user.type(screen.getByLabelText("Message"), BODY)
    await user.click(screen.getByRole("button", { name: "Send" }))
    first?.close(1006)
    await waitFor(() => expect(FakeSocket.instances.length).toBe(2))
    FakeSocket.instances[1]?.onmessage?.({
      data: JSON.stringify({ v: 1, type: "state", state: "bot", assigned_agent: null }),
    } as MessageEvent)
    FakeSocket.instances[1]?.onmessage?.({
      data: JSON.stringify({ v: 1, type: "message", id: 12, role: "visitor", body: BODY }),
    } as MessageEvent)
    FakeSocket.instances[1]?.onmessage?.({
      data: JSON.stringify({ v: 1, type: "ack", client_message_id: CLIENT_ID, id: 12 }),
    } as MessageEvent)

    await waitFor(() => expect(screen.getAllByText(BODY)).toHaveLength(1))
  })
})
