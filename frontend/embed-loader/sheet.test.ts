import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { SHEET_QUERY } from "./iframe"
import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"
const PUBLIC = "d".repeat(64)

const attachScript = () => {
  const script = document.createElement("script")
  script.src = `${WIDGET_ORIGIN}/supportchat.js`
  document.body.appendChild(script)
  return script
}

const bootstrapOk = () =>
  vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      widget: { name: "SupportChat", greeting: "Hi", privacy_url: "http://localhost:3000/privacy" },
      bootstrap_token: "boot-token",
      resume_token: "resume-1",
      conversation: { state: "prechat", assigned_agent: null, messages: [] },
    }),
  })

const stubViewport = (sheet: boolean) => {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches: query === SHEET_QUERY ? sheet : false,
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  )
}

const launcher = () => document.querySelector('[aria-label="Open chat"]') as HTMLButtonElement
const panel = () => document.querySelector("iframe") as HTMLIFrameElement

const fromWidget = (iframe: HTMLIFrameElement, data: unknown) =>
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: WIDGET_ORIGIN,
      source: iframe.contentWindow,
      data,
    }),
  )

const openPanel = async () => {
  vi.stubGlobal("fetch", bootstrapOk())
  installSupportChat(window, document, attachScript())
  launcher().click()
  await vi.waitFor(() => expect(panel()).not.toBeNull())
  fromWidget(panel(), { type: "widget.painted" })
}

describe("phone sheet layout", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    document.head.innerHTML = ""
    document.documentElement.style.overflow = ""
    vi.unstubAllGlobals()
    window.__supportchat = { siteKey: "demo", publicKey: PUBLIC }
    window.__supportchatInstalled = false
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
  })
  afterEach(() => {
    document.body.innerHTML = ""
  })

  test("the panel stylesheet turns the iframe into a full-viewport dvh sheet on small screens", async () => {
    stubViewport(true)
    await openPanel()
    const css = document.querySelector("[data-supportchat-panel-style]")?.textContent ?? ""

    expect(css).toContain(`@media ${SHEET_QUERY}`)
    expect(css).toContain("height:var(--supportchat-vvh,100dvh)!important")
    expect(css).toContain("border-radius:0!important")
    expect(css).toContain("width:100%!important")
  })

  test("the widget URL announces the sheet layout only on small screens", async () => {
    stubViewport(true)
    await openPanel()
    expect(new URL(panel().src).searchParams.get("layout")).toBe("sheet")
  })

  test("desktop keeps the floating panel with no layout hint", async () => {
    stubViewport(false)
    await openPanel()
    expect(new URL(panel().src).searchParams.get("layout")).toBeNull()
    expect(document.documentElement.style.overflow).toBe("")
  })

  test("opening the sheet locks host scroll and closing restores the host value", async () => {
    stubViewport(true)
    document.documentElement.style.overflow = "auto"
    await openPanel()
    expect(document.documentElement.style.overflow).toBe("hidden")

    fromWidget(panel(), { type: "widget.close" })
    expect(document.documentElement.style.overflow).toBe("auto")
  })

  test("the launcher shows a busy ring while the chat loads and clears the safe area", () => {
    stubViewport(true)
    vi.stubGlobal("fetch", vi.fn())
    installSupportChat(window, document, attachScript())
    const css = [...document.head.querySelectorAll("style")].map((s) => s.textContent).join("")
    expect(css).toContain("[data-supportchat-launcher][aria-busy=true]::after")
    expect(css).toContain("env(safe-area-inset-bottom)")
    expect(css).toContain("prefers-reduced-motion")
  })

  test("a host-side skeleton shows on click and is removed once the widget paints", async () => {
    stubViewport(true)
    vi.stubGlobal("fetch", bootstrapOk())
    installSupportChat(window, document, attachScript())
    launcher().click()
    const placeholder = document.querySelector("[data-supportchat-placeholder]") as HTMLElement
    expect(placeholder).not.toBeNull()
    expect(placeholder.hidden).toBe(false)
    await vi.waitFor(() => expect(panel()).not.toBeNull())
    expect(placeholder.hidden).toBe(false)
    fromWidget(panel(), { type: "widget.painted" })
    expect(placeholder.hidden).toBe(true)
    expect(panel().hidden).toBe(false)
    const css = document.querySelector("[data-supportchat-panel-style]")?.textContent ?? ""
    expect(css).toContain("[data-supportchat-placeholder]")
    expect(css).toContain("prefers-reduced-motion")
  })

  test("a failed bootstrap removes the skeleton and keeps the launcher", async () => {
    stubViewport(false)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }))
    installSupportChat(window, document, attachScript())
    const button = launcher()
    button.click()
    const placeholder = document.querySelector("[data-supportchat-placeholder]") as HTMLElement
    await vi.waitFor(() => expect(placeholder.hidden).toBe(true))
    expect(button.hidden).toBe(false)
    expect(document.documentElement.style.overflow).toBe("")
  })
})
