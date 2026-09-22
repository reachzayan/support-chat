import { staffGet } from "@/lib/auth-client"

import type {
  CannedReply,
  ConversationDetail,
  InboxCounts,
  InboxFilter,
  InboxListItem,
  InboxMessage,
} from "./types"
import { EMPTY_INBOX_COUNTS } from "./types"

export type InboxListPage = {
  items: InboxListItem[]
  next_cursor: string | null
  counts: InboxCounts
}

export const mergeInboxMessages = (...pages: InboxMessage[][]) =>
  Array.from(new Map(pages.flat().map((message) => [message.id, message])).values()).toSorted(
    (left, right) => left.id - right.id,
  )

export const fetchInboxList = async (filter: InboxFilter, cursor?: string | null) => {
  const params = new URLSearchParams({ state: filter })
  if (cursor) {
    params.set("cursor", cursor)
  }
  const response = await staffGet(`/api/conversations?${params.toString()}`)
  if (!response.ok) {
    return null
  }
  const body = (await response.json()) as {
    items: InboxListItem[]
    next_cursor?: string | null
    counts?: InboxCounts
  }
  return {
    items: body.items,
    next_cursor: body.next_cursor ?? null,
    counts: body.counts ?? EMPTY_INBOX_COUNTS,
  } satisfies InboxListPage
}

export const fetchInboxDetailPage = async (conversationId: string, beforeId?: number) => {
  const query = beforeId === undefined ? "" : `?before_id=${beforeId}`
  const response = await staffGet(`/api/conversations/${conversationId}${query}`)
  if (!response.ok) {
    return null
  }
  return (await response.json()) as ConversationDetail
}

export const fetchInboxDetail = async (conversationId: string) => {
  const detail = await fetchInboxDetailPage(conversationId)
  if (detail === null) {
    return null
  }
  const cannedResponse = await staffGet(`/api/canned-replies?site_id=${detail.site_id}`)
  const canned = cannedResponse.ok
    ? ((await cannedResponse.json()) as { items: CannedReply[] }).items
    : []
  return { detail, canned }
}
