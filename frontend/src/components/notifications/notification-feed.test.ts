import { expect, test } from "vitest"

import { applyConversationRead, applyRead, mergeFeed } from "./notification-feed"
import type { NotificationFeed } from "./types"

const feed: NotificationFeed = {
  items: [
    {
      id: 103,
      conversation_id: "a",
      site_id: "easy",
      site_name: "SampleSite",
      scenario: "visitor_message",
      created_at: "2026-10-07T12:00:03Z",
      read_at: null,
    },
    {
      id: 102,
      conversation_id: "b",
      site_id: "easy",
      site_name: "SampleSite",
      scenario: "visitor_message",
      created_at: "2026-10-07T12:00:02Z",
      read_at: null,
    },
    {
      id: 99,
      conversation_id: "a",
      site_id: "easy",
      site_name: "SampleSite",
      scenario: "visitor_message",
      created_at: "2026-10-07T12:00:01Z",
      read_at: null,
    },
  ],
  unread_count: 34,
  unread_conversations: { a: 33, b: 1 },
  next_cursor: 99,
}

// Oracle: read requests apply only through the notification ID originally observed.
// The remaining 31 older unread notifications for chat a are on unloaded pages.
test("mark all read keeps notifications arriving after the read watermark unread", () => {
  const result = applyRead(feed, 101)
  expect(result?.unread_count).toBe(2)
  expect(result?.unread_conversations).toEqual({ a: 1, b: 1 })
  expect(result?.items[0].read_at).toBeNull()
  expect(result?.items[1].read_at).toBeNull()
  expect(result?.items[2].read_at).toEqual(expect.any(String))
})

test("reading a conversation preserves its newer alert and other chats' counts", () => {
  const result = applyConversationRead(feed, "a", 101)
  expect(result?.unread_count).toBe(2)
  expect(result?.unread_conversations).toEqual({ a: 1, b: 1 })
  expect(result?.items[0].read_at).toBeNull()
  expect(result?.items[1].read_at).toBeNull()
  expect(result?.items[2].read_at).toEqual(expect.any(String))
})

test("refresh drops retired chat alerts even when an open chat still overlaps the page", () => {
  const refreshed: NotificationFeed = {
    items: [feed.items[0]],
    unread_count: 1,
    unread_conversations: { a: 1 },
    next_cursor: null,
  }
  const result = mergeFeed(feed, refreshed, false)
  expect(result.items.map((item) => item.id)).toEqual([103])
  expect(result.unread_count).toBe(1)
  expect(result.next_cursor).toBeNull()
})
