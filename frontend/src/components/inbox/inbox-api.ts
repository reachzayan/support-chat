import { staffGet } from "@/lib/auth-client"

import { parseCitations } from "./inbox-citations"
import type {
  CannedReply,
  ConversationDetail,
  InboxCounts,
  InboxFilter,
  InboxListItem,
  InboxMessage,
  InboxSite,
} from "./types"
import { EMPTY_INBOX_COUNTS } from "./types"

export type InboxListPage = {
  items: InboxListItem[]
  next_cursor: string | null
  counts: InboxCounts
  sites: InboxSite[]
}

export const mergeInboxMessages = (...pages: InboxMessage[][]) =>
  Array.from(new Map(pages.flat().map((message) => [message.id, message])).values()).toSorted(
    (left, right) => left.id - right.id,
  )

/** Keeps the first row per id so a repeated id can never reach React as a duplicate key. */
export const uniqueById = <T extends { id: string }>(rows: T[]): T[] => {
  const seen = new Set<string>()
  return rows.filter((row) => {
    if (seen.has(row.id)) {
      return false
    }
    seen.add(row.id)
    return true
  })
}

export const fetchInboxList = async (
  filter: InboxFilter,
  cursor?: string | null,
  siteId?: string | null,
) => {
  const params = new URLSearchParams({ state: filter })
  if (cursor) {
    params.set("cursor", cursor)
  }
  if (siteId) {
    params.set("site_id", siteId)
  }
  const response = await staffGet(`/api/conversations?${params.toString()}`)
  if (response.status === 400) {
    return siteId && !cursor ? ("invalid_site" as const) : null
  }
  if (!response.ok) {
    return null
  }
  const body = (await response.json()) as {
    items: InboxListItem[]
    next_cursor?: string | null
    counts?: InboxCounts
    sites?: InboxSite[]
  }
  return {
    items: uniqueById(body.items),
    next_cursor: body.next_cursor ?? null,
    counts: body.counts ?? EMPTY_INBOX_COUNTS,
    sites: body.sites ?? [],
  } satisfies InboxListPage
}

export const fetchInboxDetailPage = async (conversationId: string, beforeId?: number) => {
  const query = beforeId === undefined ? "" : `?before_id=${beforeId}`
  const response = await staffGet(`/api/conversations/${conversationId}${query}`)
  if (!response.ok) {
    return null
  }
  const detail = (await response.json()) as ConversationDetail
  for (const message of detail.messages) {
    message.citations = parseCitations(message.citations)
  }
  return detail
}

export const fetchCannedReplies = async (siteId: string) => {
  const response = await staffGet(`/api/canned-replies?site_id=${siteId}`)
  return response.ok ? ((await response.json()) as { items: CannedReply[] }).items : []
}

export const fetchInboxDetail = async (conversationId: string) => {
  const detail = await fetchInboxDetailPage(conversationId)
  if (detail === null) {
    return null
  }
  return { detail, canned: await fetchCannedReplies(detail.site_id) }
}
