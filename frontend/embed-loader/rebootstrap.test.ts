import { beforeEach, describe, expect, test, vi } from "vitest"

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"
const DEMO_KEY = "demo"
const PUBLIC = "d".repeat(64)
const RESUME = "resume-1"

const openActivated = async () => {
  window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
      bootstrap_token: "boot",
      resume_token: RESUME,
    }),
  })
  vi.stubGlobal("fetch", fetchMock)
  const script = document.createElement("script")
  script.src = `${WIDGET_ORIGIN}/supportchat.js`
  document.body.appendChild(script)
  installSupportChat(window, document, script)
  document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
  await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())
  const iframe = document.querySelector("iframe") as HTMLIFrameElement
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: WIDGET_ORIGIN,
      source: iframe.contentWindow,
      data: { type: "widget.activated" },
    }),
  )
  await vi.waitFor(() =>
    expect(window.localStorage.getItem(`supportchat.visitor.${DEMO_KEY}`)).toBe(RESUME),
  )
  return { fetchMock, iframe }
}

describe("bootstrap expiry", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
    window.__supportchatInstalled = false
  })

  test("4401 rebootstrap posts the same-site resume token once", async () => {
    const { fetchMock, iframe } = await openActivated()
    expect(window.localStorage.getItem(`supportchat.visitor.${DEMO_KEY}`)).toBe(RESUME)

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.rebootstrap" },
      }),
    )
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    const body = JSON.parse(String((fetchMock.mock.calls[1] as [string, RequestInit])[1].body)) as {
      resume_token: string
      site_key: string
    }
    expect(body.site_key).toBe(DEMO_KEY)
    expect(body.resume_token).toBe(RESUME)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
