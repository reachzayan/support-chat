import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, vi } from "vitest"

import { InboxConsole } from "@/components/inbox/inbox-console"
import type { ConversationDetail } from "@/components/inbox/types"
import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

export const ALEX = {
  id: "11111111-1111-4111-8111-000000000001",
  email: "agent@example.local",
  display_name: "Alex Morgan",
  is_admin: false,
}

export const JORDAN = {
  id: "22222222-2222-4222-8222-000000000002",
  email: "jordan@example.local",
  display_name: "Jordan Lee",
  is_admin: false,
}

export const CONVO_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
export const OTHER_CONVO = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
export const EASY_SITE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
export const BG_SITE = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
export const JOIN_LINE = "You're now chatting with Alex Morgan."
export const AGENT_HELP = "I can help with that."
export const HOURS_BODY = "Most negative results are reported within 24-48 hours."
export const STILL_THERE = "still there?"
export const CHROME_MAC =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
export const CLIENT_ID = "20000000-0000-4000-8000-000000000001"

export class FakeSocket {
  static instances: FakeSocket[] = []
  sent: string[] = []
  readyState = 1
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null

  constructor(public url: string) {
    FakeSocket.instances.push(this)
    queueMicrotask(() => this.onopen?.(new Event("open")))
  }

  send(data: string) {
    this.sent.push(data)
  }

  close(code = 1000) {
    this.onclose?.({ code } as CloseEvent)
  }
}

export const adaQueued = {
  id: CONVO_ID,
  visitor_display: "Ada Lopez",
  site_name: "SampleSite",
  state: "queued",
  preview: "How fast are DOT results?",
  last_message_at: "2026-09-09T16:00:00+00:00",
  assigned_agent: null,
}

export const adaDetail: ConversationDetail = {
  id: CONVO_ID,
  site_id: EASY_SITE,
  site_name: "SampleSite",
  state: "queued",
  inquiry_type: "results",
  intent: "turnaround",
  attention_needed: false,
  human_enabled: true,
  bot_enabled: true,
  assigned_agent: null,
  visitor: {
    name: "Ada Lopez",
    email: "ada@example.com",
    phone: null,
    ip: "203.0.113.40",
    user_agent: CHROME_MAC,
  },
  page: {
    title: "DOT screening",
    url: "https://sample-site.example.com/dot",
    referrer: "javascript:alert(1)",
  },
  messages: [
    {
      id: 1,
      role: "visitor",
      author_user: null,
      body: "How fast are DOT results?",
      source_article_ids: null,
      source_chunk_ids: null,
      created_at: "2026-09-09T16:00:00+00:00",
    },
  ],
}

export const bgQueued = {
  id: OTHER_CONVO,
  visitor_display: "Other Visitor",
  site_name: "Sample Services",
  state: "queued",
  preview: "Need a package quote",
  last_message_at: "2026-09-09T15:00:00+00:00",
  assigned_agent: null,
}

export const bgDetail: ConversationDetail = {
  ...adaDetail,
  id: OTHER_CONVO,
  site_id: BG_SITE,
  site_name: "Sample Services",
  visitor: { ...adaDetail.visitor, name: "Other Visitor", email: "other@example.com" },
  messages: [],
}

type Json = Record<string, unknown> | { items: unknown[] }

let listItems = [adaQueued, bgQueued]
let listCursor: string | null = null
let details: Record<string, ConversationDetail> = {
  [CONVO_ID]: adaDetail,
  [OTHER_CONVO]: bgDetail,
}

export const setListCursor = (next: string | null) => {
  listCursor = next
}

export const setListItems = (next: typeof listItems) => {
  listItems = next
}

export const setDetails = (next: Record<string, ConversationDetail>) => {
  details = next
}

const jsonResponse = (body: Json, status = 200) => {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

export const staffFetch = vi.fn<
  (input: RequestInfo | URL) => Promise<ReturnType<typeof jsonResponse>>
>(async (input) => {
  const url = String(input)
  if (url.includes("/api/canned-replies")) {
    const siteId = new URL(url, "http://localhost").searchParams.get("site_id")
    if (siteId === EASY_SITE) {
      return jsonResponse({ items: [{ shortcut: "hours", body: HOURS_BODY }] })
    }
    return jsonResponse({ items: [] })
  }
  const detailMatch = /\/api\/conversations\/([0-9a-f-]+)/i.exec(url)
  if (detailMatch?.[1] && !url.includes("?")) {
    const detail = details[detailMatch[1]]
    if (detail === undefined) {
      return jsonResponse({ detail: "Not found" }, 404)
    }
    return jsonResponse(detail)
  }
  if (url.includes("/api/conversations")) {
    const parsed = new URL(url, "http://localhost")
    const state = parsed.searchParams.get("state")
    const cursor = parsed.searchParams.get("cursor")
    const items = listItems.filter((item) => (state ? item.state === state : true))
    const counts = {
      human: listItems.filter((item) => item.state === "human").length,
      bot: listItems.filter((item) => item.state === "bot").length,
      queued: listItems.filter((item) => item.state === "queued").length,
      closed: listItems.filter((item) => item.state === "closed").length,
    }
    if (cursor === "page-2") {
      return jsonResponse({
        items: [
          {
            id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            visitor_display: "Third Visitor",
            site_name: "SampleSite",
            state: "queued",
            preview: "County search",
            last_message_at: "2026-09-09T14:00:00+00:00",
            assigned_agent: null,
          },
        ],
        next_cursor: null,
        counts,
      })
    }
    return jsonResponse({ items, next_cursor: listCursor, counts })
  }
  return jsonResponse({ detail: "missing" }, 404)
})

export const emit = (socket: FakeSocket | undefined, payload: unknown) => {
  socket?.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
}

export const resetInboxHarness = () => {
  FakeSocket.instances = []
  setAccessToken("jwt-alex")
  setListItems([adaQueued, bgQueued])
  setListCursor(null)
  setDetails({
    [CONVO_ID]: structuredClone(adaDetail),
    [OTHER_CONVO]: structuredClone(bgDetail),
  })
  vi.stubGlobal("WebSocket", FakeSocket)
  vi.stubGlobal("fetch", staffFetch)
  vi.stubGlobal("crypto", { ...crypto, randomUUID: () => CLIENT_ID })
  staffFetch.mockClear()
}

export const openQueuedAda = async () => {
  const user = userEvent.setup()
  renderWithProviders(<InboxConsole user={ALEX} />)
  await user.click(screen.getByRole("button", { name: "Needs Attention" }))
  await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
  await user.click(screen.getByRole("button", { name: /Ada Lopez/ }))
  await waitFor(() => expect(screen.getByText("ada@example.com")).toBeInTheDocument())
  return user
}

export const emitAlexJoined = (socket: FakeSocket | undefined) => {
  emit(socket, {
    v: 1,
    type: "state",
    state: "human",
    assigned_agent: { id: ALEX.id, display_name: ALEX.display_name },
  })
}
