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
    expect(launcher?.querySelector("img")).toBeNull()
    expect(launcher?.textContent).toBe("Chat")
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

const CHAT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

test("closed chat counts fresh replies once, plays the shared message tone, and clears on opening", async () => {
  document.body.innerHTML = ""
  window.__supportchatInstalled = false
  window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
  window.localStorage.clear()
  const played: string[] = []
  vi.stubGlobal("Notification", { permission: "denied" })
  vi.stubGlobal(
    "Audio",
    class {
      currentTime = 0
      preload = ""
      constructor(private readonly src: string) {}
      load() {}
      pause() {}
      async play() {
        played.push(this.src)
      }
    },
  )
  vi.stubGlobal("fetch", bootstrapOk("resume-1"))
  installSupportChat(window, document, attachScript())
  const launcher = document.querySelector<HTMLButtonElement>("[data-supportchat-launcher]")!
  launcher.click()
  await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())
  const iframe = document.querySelector("iframe")!
  const send = (data: unknown, origin = WIDGET_ORIGIN, source?: Window | null) =>
    window.dispatchEvent(
      new MessageEvent("message", {
        data,
        origin,
        source: source === undefined ? iframe.contentWindow : source,
      }),
    )
  send({ type: "widget.painted" })
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 1 })
  expect(launcher.getAttribute("aria-label")).toBe("Open chat")
  send({ type: "widget.close" })
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 2 }, "https://evil.test")
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 2 }, WIDGET_ORIGIN, window)
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: -1 })
  expect(launcher.getAttribute("aria-label")).toBe("Open chat")
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 2 })
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 2 })
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 3 })
  expect(launcher.getAttribute("aria-label")).toBe("Open chat, 2 unread messages")
  expect(launcher.querySelector("[data-supportchat-unread]")?.textContent).toBe("2")
  expect(played).toEqual([
    "http://widget.localhost:3000/sounds/message.wav",
    "http://widget.localhost:3000/sounds/message.wav",
  ])
  launcher.click()
  expect(launcher.getAttribute("aria-label")).toBe("Open chat")
  expect(launcher.querySelector("[data-supportchat-unread]")?.textContent).toBe("")
  send({ type: "widget.close" })
  send({ type: "widget.sound", enabled: false })
  send({ type: "widget.message", conversation_id: CHAT_ID, message_id: 4 })
  expect(launcher.getAttribute("aria-label")).toBe("Open chat, 1 unread message")
  expect(played).toHaveLength(2)
})
