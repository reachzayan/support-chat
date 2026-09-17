import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

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

const bootstrapOk = () => {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      widget: {
        name: "SupportChat demo",
        greeting: "Talk to a specialist about screening.",
        privacy_url: "http://localhost:3000/privacy",
      },
      bootstrap_token: "boot-token",
      resume_token: "resume-1",
      conversation: { state: "prechat", assigned_agent: null, messages: [] },
    }),
  })
}

const screenLauncher = () =>
  document.querySelector('[aria-label="Open chat"]') as HTMLButtonElement | null

const panel = () => document.querySelector("iframe") as HTMLIFrameElement | null

const paintPanel = (iframe: HTMLIFrameElement) => {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: WIDGET_ORIGIN,
      source: iframe.contentWindow,
      data: { type: "widget.painted" },
    }),
  )
}

const pendingBootstrap = () => {
  const box: { finish: (value: unknown) => void } = {
    finish: () => undefined,
  }
  return {
    fetchMock: vi.fn().mockReturnValue(
      new Promise((resolve) => {
        box.finish = resolve
      }),
    ),
    finish: (value: unknown) => box.finish(value),
  }
}

const resetLoader = () => {
  window.localStorage.clear()
  document.body.innerHTML = ""
  vi.unstubAllGlobals()
  window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
  window.__supportchatInstalled = false
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0)
    return 1
  })
}

describe("widget panel warmup", () => {
  beforeEach(resetLoader)
  afterEach(() => {
    document.body.innerHTML = ""
  })

  test("install preconnects the widget origin and does not create a panel", () => {
    vi.stubGlobal("fetch", vi.fn())
    installSupportChat(window, document, attachScript())

    expect(document.querySelector('link[rel="preconnect"]')?.getAttribute("href")).toBe(
      WIDGET_ORIGIN,
    )
    expect(panel()).toBeNull()
  })

  test("hover warms a hidden iframe without bootstrapping", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    installSupportChat(window, document, attachScript())
    screenLauncher()?.dispatchEvent(new Event("pointerenter"))

    await vi.waitFor(() => expect(panel()).not.toBeNull())
    expect(fetchMock).not.toHaveBeenCalled()
    expect(panel()?.hidden).toBe(true)
    expect(panel()?.style.opacity).toBe("0")
    expect(screenLauncher()?.hidden).toBe(false)
  })

  test("click starts the iframe before bootstrap returns and keeps it hidden", async () => {
    const pending = pendingBootstrap()
    vi.stubGlobal("fetch", pending.fetchMock)
    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()

    await vi.waitFor(() => expect(panel()).not.toBeNull())
    expect(panel()?.hidden).toBe(true)
    expect(panel()?.style.opacity).toBe("0")
    expect(screenLauncher()?.hidden).toBe(false)
    expect(screenLauncher()?.getAttribute("aria-busy")).toBe("true")

    pending.finish({
      ok: true,
      json: async () => ({
        widget: {
          name: "SupportChat demo",
          greeting: "Talk to a specialist about screening.",
          privacy_url: "http://localhost:3000/privacy",
        },
        bootstrap_token: "boot-token",
        resume_token: "resume-1",
        conversation: { state: "prechat", assigned_agent: null, messages: [] },
      }),
    })
    await vi.waitFor(() => expect(panel()?.hidden).toBe(true))
    expect(screenLauncher()?.hidden).toBe(false)
  })
})

describe("widget panel reveal", () => {
  beforeEach(resetLoader)
  afterEach(() => {
    document.body.innerHTML = ""
  })

  test("widget.ready does not reveal the empty panel", async () => {
    vi.stubGlobal("fetch", bootstrapOk())
    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()
    await vi.waitFor(() => expect(panel()).not.toBeNull())
    const iframe = panel() as HTMLIFrameElement
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.ready" },
      }),
    )

    expect(iframe.hidden).toBe(true)
    expect(iframe.style.opacity).toBe("0")
    expect(screenLauncher()?.hidden).toBe(false)
  })

  test("a second click before paint leaves the empty iframe hidden", async () => {
    vi.stubGlobal("fetch", bootstrapOk())
    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()
    await vi.waitFor(() => expect(panel()).not.toBeNull())
    screenLauncher()?.click()

    expect(panel()?.hidden).toBe(true)
    expect(panel()?.style.opacity).toBe("0")
    expect(screenLauncher()?.hidden).toBe(false)
  })

  test("widget.painted fades the panel in and hides the launcher", async () => {
    vi.stubGlobal("fetch", bootstrapOk())
    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()
    await vi.waitFor(() => expect(panel()).not.toBeNull())
    const iframe = panel() as HTMLIFrameElement
    paintPanel(iframe)

    expect(iframe.hidden).toBe(false)
    expect(iframe.style.opacity).toBe("1")
    expect(screenLauncher()?.hidden).toBe(true)
    expect(screenLauncher()?.getAttribute("aria-busy")).toBe("false")
  })

  test("reopen after close shows the already-painted panel", async () => {
    vi.stubGlobal("fetch", bootstrapOk())
    installSupportChat(window, document, attachScript())
    screenLauncher()?.click()
    await vi.waitFor(() => expect(panel()).not.toBeNull())
    const iframe = panel() as HTMLIFrameElement
    paintPanel(iframe)
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.close" },
      }),
    )
    expect(iframe.style.opacity).toBe("0")
    expect(screenLauncher()?.hidden).toBe(false)

    screenLauncher()?.click()
    expect(iframe.hidden).toBe(false)
    expect(iframe.style.opacity).toBe("1")
    expect(screenLauncher()?.hidden).toBe(true)
  })
})
