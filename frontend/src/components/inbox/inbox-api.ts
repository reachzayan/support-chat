import { staffGet } from "@/lib/auth-client"

import type {
  CannedReply,
  ConversationDetail,
  InboxCounts,
  InboxFilter,
  InboxListItem,
} from "./types"
import { EMPTY_INBOX_COUNTS } from "./types"

export type InboxListPage = {
  items: InboxListItem[]
  next_cursor: string | null
  counts: InboxCounts
}

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

export const fetchInboxDetail = async (conversationId: string) => {
  const response = await staffGet(`/api/conversations/${conversationId}`)
  if (!response.ok) {
    return null
  }
  const body = (await response.json()) as ConversationDetail
  const cannedResponse = await staffGet(`/api/canned-replies?site_id=${body.site_id}`)
  const canned = cannedResponse.ok
    ? ((await cannedResponse.json()) as { items: CannedReply[] }).items
    : []
  return { detail: body, canned }
}
