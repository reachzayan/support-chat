import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"
const DEMO_KEY = "demo"
const PUBLIC = "d".repeat(64)

const scriptSrc = `${WIDGET_ORIGIN}/supportchat.js`

const attachScript = () => {
  const script = document.createElement("script")
  script.src = scriptSrc
  document.body.appendChild(script)
  return script
}

const bootstrapOk = (resumeToken: string) => {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      widget: {
        name: "SupportChat demo",
        greeting: "Talk to a specialist about screening.",
        privacy_url: "http://localhost:3000/privacy",
      },
      bootstrap_token: "boot-token",
      resume_token: resumeToken,
    }),
  })
}

describe("supportchat loader", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
    window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
    window.__supportchatInstalled = false
  })

  afterEach(() => {
    document.body.innerHTML = ""
  })

  test("initialization writes no storage and sends no request", () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    const setItem = vi.spyOn(Storage.prototype, "setItem")

    installSupportChat(window, document, attachScript())

    expect(fetchMock).not.toHaveBeenCalled()
    expect(setItem).not.toHaveBeenCalled()
    expect(document.querySelector("iframe")).toBeNull()
    const launcher = screenLauncher()
    expect(launcher).not.toBeNull()
    expect(launcher?.style.width).toBe("56px")
    expect(launcher?.style.height).toBe("56px")
    expect(launcher?.style.right).toBe("24px")
    expect(launcher?.style.bottom).toBe("24px")
    expect(launcher?.style.background).toBe("rgb(11, 35, 71)")
  })

  test("first click bootstraps once and does not persist a resume token", async () => {
    const fetchMock = bootstrapOk("resume-1")
    vi.stubGlobal("fetch", fetchMock)

    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()
    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1)
    })
    await vi.waitFor(() => {
      expect(document.querySelector("iframe")).not.toBeNull()
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = init.headers as Record<string, string>
    expect(url).toBe(`${WIDGET_ORIGIN}/api/public/widget-bootstrap`)
    expect(init.method).toBe("POST")
    expect(headers["Content-Type"]).toBe("text/plain;charset=UTF-8")
    expect(window.localStorage.getItem(`supportchat.visitor.${DEMO_KEY}`)).toBeNull()
    const iframeUrl = new URL(document.querySelector("iframe")?.getAttribute("src") ?? "")
    expect(iframeUrl.origin).toBe(WIDGET_ORIGIN)
    expect(iframeUrl.pathname).toBe("/widget")
    expect(iframeUrl.searchParams.get("site_key")).toBe(DEMO_KEY)
    expect(iframeUrl.searchParams.get("public_key")).toBe(PUBLIC)
    expect(iframeUrl.searchParams.get("parent_origin")).toBe(window.location.origin)
    expect(iframeUrl.search).not.toContain("boot-token")
    expect(iframeUrl.search).not.toContain("resume-1")
    expect(document.querySelector("iframe")?.getAttribute("title")).toBe("SupportChat")
  })

  test("running the snippet twice mounts only one launcher", () => {
    vi.stubGlobal("fetch", vi.fn())

    installSupportChat(window, document, attachScript())
    installSupportChat(window, document, attachScript())

    expect(document.querySelectorAll('[aria-label="Open chat"]')).toHaveLength(1)
  })

  test("closing before Start stores nothing", async () => {
    vi.stubGlobal("fetch", bootstrapOk("resume-1"))
    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()
    await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())
    const iframe = document.querySelector("iframe") as HTMLIFrameElement
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.close" },
      }),
    )
    expect(window.localStorage.getItem(`supportchat.visitor.${DEMO_KEY}`)).toBeNull()
  })
})

const screenLauncher = () =>
  document.querySelector('[aria-label="Open chat"]') as HTMLButtonElement | null
