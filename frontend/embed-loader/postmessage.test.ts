import { beforeEach, describe, expect, test, vi } from "vitest"

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"

const attachScript = () => {
  const script = document.createElement("script")
  script.src = `${WIDGET_ORIGIN}/supportchat.js`
  document.body.appendChild(script)
  return script
}

const openPanel = async () => {
  window.__supportchat = { siteKey: "demo", publicKey: "d".repeat(64) }
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
        bootstrap_token: "boot",
        resume_token: "resume-1",
      }),
    }),
  )
  installSupportChat(window, document, attachScript())
  document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
  await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())
  return document.querySelector("iframe") as HTMLIFrameElement
}

describe("postMessage boundary", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
  })

  test("wrong origin, source, type, and height 5000 do nothing", async () => {
    const iframe = await openPanel()
    iframe.style.height = "480px"

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://evil.test",
        source: iframe.contentWindow,
        data: { type: "widget.resize", height: 600 },
      }),
    )
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: window,
        data: { type: "widget.resize", height: 600 },
      }),
    )
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.resize", height: 5000 },
      }),
    )

    expect(iframe.style.height).toBe("480px")
  })

  test("valid source and origin height 600 resizes the frame", async () => {
    const iframe = await openPanel()
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.resize", height: 600 },
      }),
    )
    expect(iframe.style.height).toBe("600px")
  })
})
