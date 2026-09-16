import { beforeEach, describe, expect, test, vi } from "vitest"

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"
const VISITOR_LINE = "How fast are results?"

describe("host isolation", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
    window.__supportchatInstalled = false
  })

  test("hostile host CSS cannot reach transcript text in the host document", async () => {
    const style = document.createElement("style")
    style.textContent = "* { color: hotpink !important }"
    document.head.appendChild(style)
    window.__supportchat = { siteKey: "demo", publicKey: "d".repeat(64) }
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
          bootstrap_token: "boot",
        }),
      }),
    )
    const script = document.createElement("script")
    script.src = `${WIDGET_ORIGIN}/supportchat.js`
    document.body.appendChild(script)
    installSupportChat(window, document, script)
    document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
    await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())

    const iframe = document.querySelector("iframe") as HTMLIFrameElement
    const iframeUrl = new URL(iframe.src)
    expect(iframeUrl.origin).toBe(WIDGET_ORIGIN)
    expect(iframeUrl.pathname).toBe("/widget")
    expect(iframeUrl.searchParams.get("site_key")).toBe("demo")
    expect(iframeUrl.searchParams.get("public_key")).toBe("d".repeat(64))
    expect(iframeUrl.searchParams.get("parent_origin")).toBe(window.location.origin)
    expect(iframeUrl.hash).toBe("")
    expect(document.body.textContent).not.toContain(VISITOR_LINE)
    expect(iframe.getAttribute("src")).not.toContain("boot")
    expect(iframe.getAttribute("src")).not.toContain("resume")

    let transcriptReadable = false
    try {
      const doc = iframe.contentDocument
      if (doc?.body?.textContent?.includes(VISITOR_LINE)) {
        transcriptReadable = true
      }
    } catch {
      transcriptReadable = false
    }
    expect(transcriptReadable).toBe(false)
  })
})
