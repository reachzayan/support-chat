import { beforeEach, describe, expect, test, vi } from "vitest"

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"

describe("loader failure copy", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
    window.__supportchat = { siteKey: "demo", publicKey: "d".repeat(64) }
  })

  test("unreadable bootstrap shows the page-unavailable message and Retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }))
    const script = document.createElement("script")
    script.src = `${WIDGET_ORIGIN}/supportchat.js`
    document.body.appendChild(script)
    installSupportChat(window, document, script)
    document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
    await vi.waitFor(() => {
      expect(document.body.textContent).toContain("Chat is not available on this page")
    })
    expect(document.querySelector('[aria-label="Retry"]')).toBeTruthy()
  })
})
