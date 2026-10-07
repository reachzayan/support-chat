import { act, fireEvent, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useEffect, type ReactElement } from "react"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { NotificationBell } from "./notification-bell"
import { NotificationPreferences } from "./notification-preferences"
import { NotificationsProvider, useNotificationState } from "./notifications-context"

const renderNotifications = (ui: ReactElement) =>
  renderWithProviders(<NotificationsProvider>{ui}</NotificationsProvider>)

const navigate = vi.fn()
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: navigate }) }))

let read = false
let enabled = true
let failWrite = false
let latestId = 41
let unreadCount = 1
let failTone = false
const sounded = vi.fn()
beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
  read = false
  enabled = true
  failWrite = false
  latestId = 41
  unreadCount = 1
  failTone = false
  sounded.mockClear()
  localStorage.clear()
  document.title = "Inbox | SupportChat"
  document.cookie = "supportchat_notification_sound=; path=/; max-age=0"
  navigate.mockClear()
  setAccessToken("staff-token")
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (init?.method && init.method !== "GET") {
      if (failWrite) return new Response("{}", { status: 503 })
      if (url.endsWith("/preferences")) enabled = JSON.parse(String(init.body)).in_app
      else read = true
      return new Response(null, { status: 204 })
    }
    if (url.endsWith("/preferences"))
      return Response.json({
        sites: [
          {
            site_id: "easy",
            site_name: "SampleSite",
            scenarios: {
              live: true,
              bot: false,
              needs_attention: enabled,
              visitor_message: true,
              closed: false,
            },
          },
        ],
      })
    return Response.json({
      items: [
        {
          id: latestId,
          site_id: "easy",
          site_name: "SampleSite",
          conversation_id: "chat-1",
          scenario: "needs_attention",
          created_at: "2026-10-06T12:00:00Z",
          read_at: read ? "2026-10-06T12:01:00Z" : null,
        },
      ],
      unread_conversations: read ? {} : { "chat-1": unreadCount },
      unread_count: read ? 0 : unreadCount,
      next_cursor: null,
    })
  })
})
afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

test("an explicit sound preview remains audible when message tones are muted", async () => {
  enableAudio()
  // In-app audio does not depend on native notification permission or push.
  vi.stubGlobal("Notification", { permission: "denied" })
  localStorage.setItem("supportchat.push", "muted-device")
  const user = userEvent.setup()
  renderNotifications(<NotificationPreferences />)
  const tone = await screen.findByRole("switch", { name: "Message tone" })
  await user.click(tone)
  expect(tone).not.toBeChecked()
  await user.click(screen.getByRole("button", { name: "Test sound" }))
  await waitFor(() => expect(sounded).toHaveBeenCalledWith("/sounds/message.wav"))
  expect(localStorage.getItem("supportchat.push")).toBe("muted-device")
  expect(tone).not.toBeChecked()
  expect(screen.getByRole("status")).toHaveTextContent("Test sound playing")
})

test("a failed sound test shows recovery without misreporting an allowed browser permission", async () => {
  enableAudio()
  failTone = true
  const user = userEvent.setup()
  renderNotifications(<NotificationPreferences />)
  await user.click(await screen.findByRole("button", { name: "Test sound" }))
  expect(await screen.findByRole("status")).toHaveTextContent("Could not play the test sound")
  expect(screen.getByText("Browser permission: Allowed")).toBeInTheDocument()
  expect(screen.getByRole("switch", { name: "Message tone" })).toBeChecked()
})

test.each([
  {
    platform: "Chrome on macOS",
    agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/154.0.0.0 Safari/537.36",
    status: "Test sound playing",
    native: [],
    audio: ["/sounds/message.wav"],
  },
  {
    platform: "Safari on macOS",
    agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Version/26.0 Safari/605.1.15",
    status: "Native sound test sent",
    native: [false],
    audio: [],
  },
  {
    platform: "Chrome on Windows",
    agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/154.0.0.0 Safari/537.36",
    status: "Native sound test sent",
    native: [false],
    audio: [],
  },
])(
  "sound preview uses native sound where possible on $platform",
  async ({ agent, status, native, audio }) => {
    enableAudio()
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(agent)
    const alerts: NotificationOptions[] = []
    vi.stubGlobal(
      "Notification",
      class {
        static permission = "granted"
        constructor(_title: string, options: NotificationOptions) {
          alerts.push(options)
        }
        addEventListener() {}
      },
    )
    const user = userEvent.setup()
    renderNotifications(<NotificationPreferences />)
    await user.click(await screen.findByRole("button", { name: "Test sound" }))
    expect(await screen.findByRole("status")).toHaveTextContent(status)
    expect(alerts.map((options) => options.silent)).toEqual(native)
    expect(sounded.mock.calls.map(([source]) => source)).toEqual(audio)
  },
)

test.each([true, false])(
  "delivered push test respects message tone setting %s without adding inbox activity",
  async (sound) => {
    enableAudio()
    vi.stubGlobal("Notification", { permission: "denied" })
    const descriptor = Object.getOwnPropertyDescriptor(navigator, "serviceWorker")
    const worker = Object.assign(new EventTarget(), { getRegistration: async () => undefined })
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: worker })
    const view = renderNotifications(
      <>
        <NotificationBell />
        <NotificationPreferences />
      </>,
    )
    try {
      const user = userEvent.setup()
      const toggle = await screen.findByRole("switch", { name: "Message tone" })
      if (!sound) await user.click(toggle)
      expect(toggle.getAttribute("aria-checked")).toBe(String(sound))
      await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }))
      await user.click(screen.getByRole("button", { name: "Close panel" }))
      act(() => {
        worker.dispatchEvent(new MessageEvent("message", { data: { type: "supportchat.push.test" } }))
      })
      await waitFor(() => expect(sounded).toHaveBeenCalledTimes(sound ? 1 : 0))
      expect(screen.getByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument()
      expect(screen.queryByRole("button", { name: "View chat" })).not.toBeInTheDocument()
    } finally {
      view.unmount()
      if (descriptor) Object.defineProperty(navigator, "serviceWorker", descriptor)
      else Reflect.deleteProperty(navigator, "serviceWorker")
    }
  },
)

test("sound preview waits for the media device to accept playback", async () => {
  vi.stubGlobal("Notification", undefined)
  const playback = Promise.withResolvers<void>()
  vi.stubGlobal(
    "Audio",
    class {
      currentTime = 0
      preload = ""
      load() {}
      pause() {}
      play() {
        return playback.promise
      }
    },
  )
  const user = userEvent.setup()
  renderNotifications(<NotificationPreferences />)
  await user.click(await screen.findByRole("button", { name: "Test sound" }))
  expect(screen.getByRole("button", { name: "Testing…" })).toBeDisabled()
  expect(screen.queryByRole("status")).not.toBeInTheDocument()
  playback.resolve()
  expect(await screen.findByRole("status")).toHaveTextContent("Test sound playing")
  expect(screen.getByRole("button", { name: "Test sound" })).toBeEnabled()
})

test.each([320, 390, 1440])(
  "notification panel at %i px opens a conversation and persists its read status",
  async (width) => {
    vi.stubGlobal("innerWidth", width)
    const user = userEvent.setup()
    renderNotifications(<NotificationBell />)
    await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }))
    const panel = await screen.findByRole("dialog", { name: "Notifications" })
    expect(within(panel).getByRole("link", { name: "Preferences" })).toHaveAttribute(
      "href",
      "/admin/notifications",
    )
    await user.click(within(panel).getByRole("button", { name: /Needs attention.*SampleSite/ }))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/admin/inbox?conversation=chat-1"))
    expect(
      await screen.findByRole("button", { name: "Notifications, 0 unread" }),
    ).toBeInTheDocument()
    expect(read).toBe(true)
  },
)

test("the mobile notification drawer dismisses without changing unread messages", async () => {
  vi.stubGlobal("innerWidth", 390)
  const user = userEvent.setup()
  renderNotifications(<NotificationBell />)
  const trigger = await screen.findByRole("button", { name: "Notifications, 1 unread" })
  await user.click(trigger)
  await screen.findByRole("dialog", { name: "Notifications" })
  await user.click(screen.getByRole("button", { name: "Close panel" }))
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  expect(trigger).toHaveFocus()
  expect(trigger).toHaveAttribute("aria-expanded", "false")
  expect(read).toBe(false)
  expect(navigate).not.toHaveBeenCalled()
})

test("preference persists and a failed change keeps the saved choice", async () => {
  const user = userEvent.setup()
  const view = renderNotifications(<NotificationPreferences />)
  const toggle = await screen.findByRole("switch", { name: "Needs attention for SampleSite" })
  await user.click(toggle)
  await waitFor(() => expect(toggle).not.toBeChecked())
  view.unmount()
  renderNotifications(<NotificationPreferences />)
  const saved = await screen.findByRole("switch", { name: "Needs attention for SampleSite" })
  expect(saved).not.toBeChecked()
  failWrite = true
  await user.click(saved)
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not save")
  expect(saved).not.toBeChecked()
})

test("a failed mark-all-read leaves the unread badge and history intact", async () => {
  const user = userEvent.setup()
  renderNotifications(<NotificationBell />)
  await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }))
  failWrite = true
  await user.click(screen.getByRole("button", { name: "Mark all read" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not update notifications")
  expect(read).toBe(false)
  await user.click(screen.getByRole("button", { name: "Close panel" }))
  expect(await screen.findByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument()
})

test("notifications arriving after an empty feed retain access to older pages", async () => {
  let arrived = false
  vi.stubGlobal("fetch", async () =>
    Response.json({
      items: arrived
        ? [
            {
              id: 100,
              site_id: "easy",
              site_name: "SampleSite",
              conversation_id: "chat-1",
              scenario: "needs_attention",
              created_at: "2026-10-06T12:00:00Z",
              read_at: null,
            },
          ]
        : [],
      unread_count: arrived ? 31 : 0,
      next_cursor: arrived ? 71 : null,
    }),
  )
  const user = userEvent.setup()
  renderNotifications(<NotificationBell />)
  await screen.findByRole("button", { name: "Notifications, 0 unread" })
  arrived = true
  fireEvent(window, new Event("online"))
  await user.click(await screen.findByRole("button", { name: "Notifications, 31 unread" }))
  expect(screen.getByRole("button", { name: "Load older notifications" })).toBeInTheDocument()
})

const enableAudio = () => {
  vi.stubGlobal("Notification", { permission: "granted" })
  vi.stubGlobal(
    "Audio",
    class {
      currentTime = 0
      preload = ""
      constructor(private readonly src: string) {}
      load() {}
      pause() {}
      async play() {
        if (failTone) throw new DOMException("Sound blocked", "NotAllowedError")
        sounded(this.src)
      }
    },
  )
}

test("the tab count follows unread state and clears after reading", async () => {
  const user = userEvent.setup()
  renderNotifications(<NotificationBell />)
  await screen.findByRole("button", { name: "Notifications, 1 unread" })
  await waitFor(() => expect(document.title).toBe("(1) Inbox | SupportChat"))
  document.title = "Settings | SupportChat"
  await waitFor(() => expect(document.title).toBe("(1) Settings | SupportChat"))
  await user.click(screen.getByRole("button", { name: "Notifications, 1 unread" }))
  await user.click(screen.getByRole("button", { name: "Mark all read" }))
  await waitFor(() => expect(document.title).toBe("Settings | SupportChat"))
})

test("new activity produces one tone and an actionable shadcn toast; history and repeat polls stay silent", async () => {
  enableAudio()
  vi.stubGlobal("Notification", { permission: "denied" })
  localStorage.setItem("supportchat.push", "device-a")
  const user = userEvent.setup()
  renderNotifications(<NotificationBell />)
  await screen.findByRole("button", { name: "Notifications, 1 unread" })
  expect(sounded).not.toHaveBeenCalled()
  expect(screen.queryByText("Needs attention")).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Notifications, 1 unread" }))
  await user.click(screen.getByRole("button", { name: "Close panel" }))
  latestId = 42
  fireEvent(window, new Event("online"))
  await waitFor(() => expect(sounded).toHaveBeenCalledTimes(1))
  const view = await screen.findByRole("button", { name: "View chat" })
  expect(view.closest('[data-slot="toast"]')).not.toBeNull()
  fireEvent(window, new Event("online"))
  await user.click(view)
  expect(navigate).toHaveBeenCalledWith("/admin/inbox?conversation=chat-1")
  expect(sounded).toHaveBeenCalledTimes(1)
})

test("the settings switch persists mute and suppresses tones while keeping toasts", async () => {
  enableAudio()
  const user = userEvent.setup()
  renderNotifications(
    <>
      <NotificationBell />
      <NotificationPreferences />
    </>,
  )
  const toggle = await screen.findByRole("switch", { name: "Message tone" })
  expect(toggle).toBeChecked()
  await user.click(toggle)
  expect(toggle).not.toBeChecked()
  expect(document.cookie).toContain("supportchat_notification_sound=false")
  latestId = 42
  fireEvent(window, new Event("online"))
  expect(await screen.findByRole("button", { name: "View chat" })).toBeInTheDocument()
  expect(sounded).not.toHaveBeenCalled()
})

test("an unavailable audio device cannot block new notifications or their count", async () => {
  enableAudio()
  const user = userEvent.setup()
  renderNotifications(<NotificationBell />)
  await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }))
  await user.click(screen.getByRole("button", { name: "Close panel" }))
  failTone = true
  latestId = 42
  unreadCount = 2
  fireEvent(window, new Event("online"))
  expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "View chat" })).toBeInTheDocument()
  expect(sounded).not.toHaveBeenCalled()
})

const OpenConversation = () => {
  const { setActiveConversation } = useNotificationState()
  useEffect(() => {
    setActiveConversation("chat-1")
    return () => setActiveConversation(null)
  }, [setActiveConversation])
  return <p>Chat is open</p>
}

test("opening a chat reads push-only activity and retries a failed read on the next refresh", async () => {
  let latest = 70
  let saved = false
  let unavailable = true
  const boundaries: number[] = []
  const writes: string[] = []
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      writes.push(String(input))
      boundaries.push(JSON.parse(String(init.body)).through_id)
      if (unavailable) return new Response(null, { status: 503 })
      saved = true
      return new Response(null, { status: 204 })
    }
    return Response.json({
      items: [],
      unread_count: 0,
      unread_conversations: {},
      next_cursor: null,
      latest_id: latest,
    })
  })
  renderNotifications(
    <>
      <NotificationBell />
      <OpenConversation />
    </>,
  )
  await waitFor(() => expect(boundaries).toEqual([70]))
  unavailable = false
  fireEvent(window, new Event("online"))
  await waitFor(() => expect(saved).toBe(true))
  expect(boundaries).toEqual([70, 70])
  saved = false
  latest = 71
  fireEvent(window, new Event("online"))
  await waitFor(() => expect(saved).toBe(true))
  expect(boundaries).toEqual([70, 70, 71])
  expect(writes).toHaveLength(3)
  for (const url of writes) expect(url).toContain("/conversations/chat-1/read")
  expect(screen.getByRole("button", { name: "Notifications, 0 unread" })).toBeInTheDocument()
})

test("opening a chat clears all its notifications and incoming activity stays read while visible", async () => {
  unreadCount = 32
  renderNotifications(
    <>
      <NotificationBell />
      <OpenConversation />
    </>,
  )
  await screen.findByText("Chat is open")
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Notifications, 0 unread" })).toBeInTheDocument(),
  )
  expect(read).toBe(true)
  read = false
  latestId = 42
  unreadCount = 1
  fireEvent(window, new Event("online"))
  await waitFor(() => expect(read).toBe(true))
  expect(screen.queryByRole("button", { name: "View chat" })).not.toBeInTheDocument()
})
