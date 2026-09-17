export type StaffUser = {
  id: string
  email: string
  display_name: string
  is_admin: boolean
}

export type AssignedAgent = {
  id: string
  display_name: string
}

export type InboxListItem = {
  id: string
  visitor_display: string
  site_name: string
  state: string
  preview: string
  last_message_at: string
  assigned_agent: AssignedAgent | null
}

export type InboxMessage = {
  id: number
  role: string
  author_user: AssignedAgent | null
  body: string
  source_article_ids: string[] | null
  source_chunk_ids: string[] | null
  source_urls?: string[] | null
  display_locator?: string | null
  source_title?: string | null
  system_reason?: string | null
  created_at: string
  citations?: Array<{
    source_urls?: string[] | null
    source_title?: string | null
  }>
}

export type ConversationDetail = {
  id: string
  site_id: string
  site_name: string
  state: string
  inquiry_type: string | null
  intent: string | null
  attention_needed: boolean
  escalation_reason?: string | null
  human_enabled: boolean
  bot_enabled: boolean
  assigned_agent: AssignedAgent | null
  visitor: {
    name: string | null
    email: string | null
    phone: string | null
    ip: string | null
    user_agent: string | null
  }
  page: {
    title: string | null
    url: string | null
    referrer: string | null
  }
  messages: InboxMessage[]
}

export type CannedReply = {
  shortcut: string
  body: string
  scope: "general" | "website"
}

export type InboxFilter = "human" | "bot" | "queued" | "closed"

export type InboxCounts = Record<InboxFilter, number>

export const EMPTY_INBOX_COUNTS: InboxCounts = {
  human: 0,
  bot: 0,
  queued: 0,
  closed: 0,
}

export const INBOX_FILTERS: { id: InboxFilter; label: string }[] = [
  { id: "human", label: "Live" },
  { id: "bot", label: "Bot" },
  { id: "queued", label: "Needs Attention" },
  { id: "closed", label: "Closed" },
]

export const INBOX_LIST_POLL_MS = 15_000
