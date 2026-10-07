import type { NotificationFeed } from "./types"

export const mergeFeed = (
  current: NotificationFeed | null,
  next: NotificationFeed,
  older: boolean,
): NotificationFeed => {
  // A fresh page is authoritative: closed chats can disappear between polls.
  if (!older || !current || current.items.length === 0) return next
  const items = new Map(current.items.map((item) => [item.id, item]))
  for (const item of next.items) items.set(item.id, item)
  return {
    ...next,
    items: [...items.values()].toSorted((a, b) => b.id - a.id),
    next_cursor: next.next_cursor,
  }
}

export const applyRead = (
  current: NotificationFeed | null,
  through: number,
  id?: number,
): NotificationFeed | null => {
  if (!current) return current
  const now = new Date().toISOString()
  const wasUnread = current.items.some((item) => item.id === id && !item.read_at)
  const newer = unreadAfter(current, through)
  const remainingCounts = newer.reduce<Record<string, number>>((counts, item) => {
    counts[item.conversation_id] = (counts[item.conversation_id] ?? 0) + 1
    return counts
  }, {})
  return {
    ...current,
    unread_count: id ? Math.max(0, current.unread_count - Number(wasUnread)) : newer.length,
    unread_conversations: id ? decrementConversation(current, id, wasUnread) : remainingCounts,
    items: current.items.map((item) => {
      const matches = id ? item.id === id : item.id <= through
      return matches && !item.read_at ? { ...item, read_at: now } : item
    }),
  }
}

const unreadAfter = (feed: NotificationFeed, through: number) =>
  feed.items.filter((item) => item.id > through && !item.read_at)

const decrementConversation = (feed: NotificationFeed, id: number, unread: boolean) => {
  const counts = { ...feed.unread_conversations }
  const chatId = feed.items.find((item) => item.id === id)?.conversation_id
  if (chatId && unread) {
    counts[chatId] = Math.max(0, (counts[chatId] ?? 0) - 1)
    if (!counts[chatId]) delete counts[chatId]
  }
  return counts
}

export const applyConversationRead = (
  feed: NotificationFeed | null,
  chatId: string,
  through: number,
) => {
  if (!feed) return feed
  const counts = { ...feed.unread_conversations }
  const removed =
    counts[chatId] ??
    feed.items.filter((item) => item.conversation_id === chatId && !item.read_at).length
  const remaining = unreadAfter(feed, through).filter(
    (item) => item.conversation_id === chatId,
  ).length
  if (remaining) counts[chatId] = remaining
  else delete counts[chatId]
  return {
    ...feed,
    unread_count: Math.max(0, feed.unread_count - removed + remaining),
    unread_conversations: counts,
    items: feed.items.map((item) =>
      item.conversation_id === chatId && item.id <= through && !item.read_at
        ? { ...item, read_at: new Date().toISOString() }
        : item,
    ),
  }
}
