export const scenarios = [
  {
    id: "needs_attention",
    label: "Needs attention",
    description: "A visitor needs a specialist or a callback.",
  },
  { id: "live", label: "Live chats", description: "Another specialist joins a conversation." },
  {
    id: "visitor_message",
    label: "Visitor replies",
    description: "A new message in a chat assigned to you.",
  },
  {
    id: "bot",
    label: "Bot conversations",
    description: "A visitor starts or resumes an assistant conversation.",
  },
  {
    id: "closed",
    label: "Closed chats",
    description: "A chat closes automatically or is closed by someone else.",
  },
] as const

export type Scenario = (typeof scenarios)[number]["id"]
export type NotificationItem = {
  id: number
  site_id: string
  site_name: string
  conversation_id: string
  scenario: Scenario
  created_at: string
  read_at: string | null
}
export type NotificationFeed = {
  items: NotificationItem[]
  unread_count: number
  unread_conversations?: Record<string, number>
  next_cursor: number | null
  latest_id?: number | null
}
export type PushPreferences = { enabled: boolean; scenarios: Scenario[] }
export type SitePreferences = {
  site_id: string
  site_name: string
  scenarios: Record<Scenario, boolean>
  push: PushPreferences
}
export const notificationTitle: Record<Scenario, string> = {
  needs_attention: "Needs attention",
  live: "Live chat started",
  visitor_message: "New visitor reply",
  bot: "New bot conversation",
  closed: "Chat closed",
}
