import { act, fireEvent, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { NotificationBell } from "@/components/notifications/notification-bell"
import { NotificationsProvider } from "@/components/notifications/notifications-context"
import { renderWithProviders } from "@/test/render"

import { InboxConsole } from "./inbox-console"
import {
  ALEX,
  CONVO_ID,
  EASY_SITE,
  BG_SITE,
  OTHER_CONVO,
  resetInboxHarness,
  setDetails,
  staffFetch,
} from "./inbox-test-harness"

const router = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock("next/navigation", () => ({ useRouter: () => router }))
let readB = false
let readA = false
const notificationFeed = () => {
  return Response.json({
    items: [
      {
        id: 3,
        conversation_id: OTHER_CONVO,
        scenario: "needs_attention",
        read_at: readB ? "2026-10-06T12:01:00Z" : null,
        site_id: BG_SITE,
        site_name: "Sample Services",
        created_at: "2026-10-06T12:00:00Z",
      },
      {
        id: 2,
        conversation_id: CONVO_ID,
        scenario: "visitor_message",
        read_at: readA ? "2026-10-06T12:01:00Z" : null,
        site_id: EASY_SITE,
        site_name: "SampleSite",
        created_at: "2026-10-06T12:00:00Z",
      },
      {
        id: 1,
        conversation_id: CONVO_ID,
        scenario: "needs_attention",
        read_at: readA ? "2026-10-06T12:01:00Z" : null,
        site_id: EASY_SITE,
        site_name: "SampleSite",
        created_at: "2026-10-06T12:00:00Z",
      },
    ],
    unread_count: (readA ? 0 : 2) + (readB ? 0 : 1),
    unread_conversations: {
      ...(readA ? {} : { [CONVO_ID]: 2 }),
      ...(readB ? {} : { [OTHER_CONVO]: 1 }),
    },
    unread_conversation_context: {
      [CONVO_ID]: { site_id: EASY_SITE, state: "queued" },
      [OTHER_CONVO]: { site_id: BG_SITE, state: "queued" },
    },
    next_cursor: null,
  })
}
beforeEach(() => {
  resetInboxHarness()
  readA = false
  readB = false
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (!url.startsWith("/api/notifications")) return staffFetch(input, init)
    if (init?.method === "POST") {
      if (url === `/api/notifications/conversations/${CONVO_ID}/read`) readA = true
      if (url === `/api/notifications/conversations/${OTHER_CONVO}/read`) readB = true
      return new Response(null, { status: 204 })
    }
    return notificationFeed()
  })
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
const renderInbox = () =>
  renderWithProviders(
    <NotificationsProvider>
      <NotificationBell />
      <InboxConsole user={ALEX} />
    </NotificationsProvider>,
  )

test("Needs Attention shows unread activity while Live is selected and updates after opening a chat", async () => {
  const user = userEvent.setup()
  renderInbox()
  const queued = await screen.findByRole("button", { name: "Needs Attention, 3 unread" })
  expect(screen.getByRole("button", { name: "Live" })).toHaveAttribute("aria-pressed", "true")
  expect(within(queued).getByText("3", { selector: '[aria-hidden="true"]' })).toBeVisible()
  await user.click(queued)
  await user.click(await screen.findByRole("button", { name: /Ada Lopez.*2 unread notifications/ }))
  await screen.findByRole("button", { name: "Needs Attention, 1 unread" })
})

test("filter unread counts follow the website selection without reading other websites", async () => {
  const user = userEvent.setup()
  renderInbox()
  await screen.findByRole("button", { name: "Needs Attention, 3 unread" })
  await user.click(screen.getByRole("combobox", { name: "Inbox" }))
  await user.click(screen.getByRole("option", { name: "SampleSite 1" }))
  expect(screen.getByRole("button", { name: "Needs Attention, 2 unread" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument()
})

test("conversation rows show unread activity and opening Ada clears Ada's entire count only", async () => {
  const user = userEvent.setup()
  renderInbox()
  await user.click(screen.getByRole("button", { name: "Needs Attention" }))
  const ada = await screen.findByRole("button", { name: /Ada Lopez.*2 unread notifications/ })
  expect(within(ada).getByText("2", { selector: '[aria-hidden="true"]' })).toBeInTheDocument()
  expect(
    screen.getByRole("button", { name: /Other Visitor.*1 unread notifications/ }),
  ).toBeInTheDocument()
  await user.click(ada)
  await screen.findByRole("log", { name: "Transcript" })
  await screen.findByRole("button", { name: "Notifications, 1 unread" })
  expect(readA).toBe(true)
  expect(
    screen.getByRole("button", { name: /Other Visitor.*1 unread notifications/ }),
  ).toBeInTheDocument()
  expect(
    within(screen.getByRole("button", { name: /Ada Lopez/ })).queryByText("2 unread notifications"),
  ).not.toBeInTheDocument()
})

test("a failed transcript load leaves its unread marker and notification count intact", async () => {
  setDetails({})
  const user = userEvent.setup()
  renderInbox()
  await user.click(screen.getByRole("button", { name: "Needs Attention" }))
  await user.click(await screen.findByRole("button", { name: /Ada Lopez.*2 unread notifications/ }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not open conversation")
  expect(screen.getByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument()
  expect(readA).toBe(false)
})

test("a chat in a hidden tab stays unread until its transcript becomes visible", async () => {
  const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(true)
  const user = userEvent.setup()
  renderInbox()
  await user.click(screen.getByRole("button", { name: "Needs Attention" }))
  await user.click(await screen.findByRole("button", { name: /Ada Lopez.*2 unread notifications/ }))
  await screen.findByRole("log", { name: "Transcript" })
  expect(readA).toBe(false)
  expect(screen.getByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument()
  hidden.mockReturnValue(false)
  fireEvent(document, new Event("visibilitychange"))
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument(),
  )
})

test("switching chats while the first read is pending still marks the second chat read", async () => {
  const fetchBoundary = window.fetch
  let release: (() => void) | undefined
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    if (
      String(input) === `/api/notifications/conversations/${CONVO_ID}/read` &&
      init?.method === "POST"
    ) {
      await new Promise<void>((resolve) => {
        release = resolve
      })
    }
    return fetchBoundary(input, init)
  })
  const user = userEvent.setup()
  renderInbox()
  await user.click(screen.getByRole("button", { name: "Needs Attention" }))
  await user.click(await screen.findByRole("button", { name: /Ada Lopez.*2 unread notifications/ }))
  await screen.findByRole("log", { name: "Transcript" })
  await waitFor(() => expect(typeof release).toBe("function"))
  await user.click(screen.getByRole("button", { name: /Other Visitor.*1 unread notifications/ }))
  await screen.findByText("other@example.com")
  await act(async () => {
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0))
  })
  expect(screen.getByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument()
  release?.()
  await screen.findByRole("button", { name: "Notifications, 0 unread" })
  expect(readA).toBe(true)
  expect(readB).toBe(true)
})
