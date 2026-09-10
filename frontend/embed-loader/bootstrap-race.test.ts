import { beforeEach, describe, expect, test, vi } from "vitest"

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"
const DEMO_KEY = "demo"
const PUBLIC = "d".repeat(64)

const attachScript = () => {
  const script = document.createElement("script")
  script.src = `${WIDGET_ORIGIN}/supportchat.js`
  document.body.appendChild(script)
  return script
}

describe("bootstrap race", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
    window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
  })

  test("widget.ready retries bootstrap until the iframe receives host.bootstrap", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        widget: {
          name: "SupportChat demo",
          greeting: "Talk to a specialist about screening.",
          privacy_url: "http://localhost:3000/privacy",
        },
        bootstrap_token: "boot-token",
        resume_token: "resume-1",
      }),
    })
    vi.stubGlobal("fetch", fetchMock)
    const posted: unknown[] = []

    installSupportChat(window, document, attachScript())
    document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
    await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())

    const iframe = document.querySelector("iframe") as HTMLIFrameElement
    Object.defineProperty(iframe, "contentWindow", {
      configurable: true,
      value: {
        postMessage: (frame: unknown) => {
          posted.push(frame)
        },
      },
    })

    posted.length = 0
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.ready" },
      }),
    )

    await vi.waitFor(() =>
      expect(
        posted.filter((frame) => (frame as { type: string }).type === "host.bootstrap").length,
      ).toBeGreaterThanOrEqual(2),
    )
  })
})
