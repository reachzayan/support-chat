import { beforeEach, describe, expect, test, vi } from "vitest"
/* oxlint-disable max-lines-per-function -- storage lifecycle cases share one isolated setup */

import { installSupportChat } from "./install"

const WIDGET_ORIGIN = "http://widget.localhost:3000"
const DEMO_KEY = "demo"
const EASY_KEY = "samplesite"
const BG_KEY = "backgroundchecks"
const PUBLIC = "d".repeat(64)
const EASY_TOKEN = "easy-token"

const attachScript = () => {
  const script = document.createElement("script")
  script.src = `${WIDGET_ORIGIN}/supportchat.js`
  document.body.appendChild(script)
  return script
}

describe("site-keyed resume storage", () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.body.innerHTML = ""
    vi.unstubAllGlobals()
    window.__supportchatInstalled = false
  })

  test("Sample Services bootstrap does not send an SampleSite token", async () => {
    window.localStorage.setItem(`supportchat.visitor.${EASY_KEY}`, EASY_TOKEN)
    window.__supportchat = { siteKey: BG_KEY, publicKey: PUBLIC }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        widget: { name: "Sample Services", greeting: "Hi", privacy_url: "http://example.com/p" },
        bootstrap_token: "boot",
        resume_token: "bg-token",
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    installSupportChat(window, document, attachScript())
    document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const body = String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body)
    expect(body).not.toContain(EASY_TOKEN)
    expect(body).toContain(BG_KEY)
  })

  test("SampleSite return sends the stored SampleSite token", async () => {
    window.localStorage.setItem(`supportchat.visitor.${EASY_KEY}`, EASY_TOKEN)
    window.__supportchat = { siteKey: EASY_KEY, publicKey: PUBLIC }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        widget: { name: "SampleSite", greeting: "Hi", privacy_url: "http://example.com/p" },
        bootstrap_token: "boot",
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    installSupportChat(window, document, attachScript())
    document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const body = String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body)
    expect(body).toContain(EASY_TOKEN)
    expect(JSON.parse(body).resume_token).toBe(EASY_TOKEN)
  })

  test("widget.activated stores only the pending resume token", async () => {
    window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
        bootstrap_token: "boot",
        resume_token: "resume-1",
      }),
    })
    vi.stubGlobal("fetch", fetchMock)
    installSupportChat(window, document, attachScript())
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
      expect(window.localStorage.getItem(`supportchat.visitor.${DEMO_KEY}`)).toBe("resume-1"),
    )
    expect(JSON.stringify(window.localStorage)).not.toContain("Ada Lopez")
  })

  test("delete all revokes the saved token and does not persist the replacement before Start", async () => {
    window.localStorage.setItem(`supportchat.visitor.${DEMO_KEY}`, "old-resume")
    window.__supportchat = { siteKey: DEMO_KEY, publicKey: PUBLIC }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mode: "identity",
          widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
          identity: {
            display_name: "Ada L.",
            email_hint: "a•••@example.com",
            phone_hint: null,
            chat_count: 1,
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mode: "forgotten",
          widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mode: "conversation",
          widget: { name: "SupportChat demo", greeting: "Hi", privacy_url: "http://example.com/p" },
          bootstrap_token: "new-boot",
          resume_token: "new-resume",
          conversation: { state: "prechat", assigned_agent: null, messages: [] },
        }),
      })
    vi.stubGlobal("fetch", fetchMock)

    installSupportChat(window, document, attachScript())
    document.querySelector<HTMLButtonElement>('[aria-label="Open chat"]')?.click()
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await vi.waitFor(() => expect(document.querySelector("iframe")).not.toBeNull())
    const iframe = document.querySelector("iframe") as HTMLIFrameElement
    const postMessage = vi.spyOn(iframe.contentWindow as Window, "postMessage")
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.ready" },
      }),
    )
    await vi.waitFor(() =>
      expect(
        postMessage.mock.calls.some(
          (call) => (call[0] as { type?: string }).type === "host.identity",
        ),
      ).toBe(true),
    )
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: WIDGET_ORIGIN,
        source: iframe.contentWindow,
        data: { type: "widget.delete_all" },
      }),
    )

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toMatchObject({
      action: "forget",
      resume_token: "old-resume",
    })
    expect(JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body))).toMatchObject({
      action: "identify",
      resume_token: null,
    })
    expect(window.localStorage.getItem(`supportchat.visitor.${DEMO_KEY}`)).toBeNull()
  })
})
