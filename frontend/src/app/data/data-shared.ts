import type { AssignedAgent } from "@/components/inbox/types"

export type SubmissionVisitor = {
  name: string | null
  email: string | null
  phone: string | null
  ip: string | null
  user_agent: string | null
  geo_country: string | null
  geo_region: string | null
  location: string | null
  created_at: string
}

export type SubmissionRow = {
  id: string
  site_id: string
  site_key: string
  site_name: string
  state: string
  inquiry_type: string | null
  intent: string | null
  attention_needed: boolean
  opening_message: string | null
  assigned_agent: AssignedAgent | null
  visitor: SubmissionVisitor
  page: {
    title: string | null
    url: string | null
    referrer: string | null
  }
  created_at: string
  last_message_at: string
  closed_at: string | null
  blocked: boolean
  block_id: string | null
}

export const STATE_LABEL: Record<string, string> = {
  prechat: "Prechat",
  bot: "Bot",
  queued: "Needs Attention",
  human: "Live",
  closed: "Closed",
}

export const COLUMNS = [
  "Name",
  "Email",
  "Phone",
  "Inquiry",
  "Intent",
  "State",
  "Site",
  "Site key",
  "Opening message",
  "Page title",
  "Page URL",
  "Referrer",
  "IP",
  "Location",
  "User agent",
  "Country",
  "Region",
  "Attention",
  "Assigned",
  "Visitor since",
  "Chat started",
  "Last message",
  "Closed",
  "Transcript",
  "Block",
] as const

export type ColumnLabel = (typeof COLUMNS)[number]

export const EXPORT_COLUMNS = COLUMNS.filter(
  (column) => column !== "Transcript" && column !== "Block",
)

export const DEFAULT_WIDTHS: Record<ColumnLabel, number> = {
  Name: 148,
  Email: 188,
  Phone: 120,
  Inquiry: 104,
  Intent: 104,
  State: 100,
  Site: 140,
  "Site key": 112,
  "Opening message": 220,
  "Page title": 160,
  "Page URL": 220,
  Referrer: 180,
  IP: 132,
  Location: 220,
  "User agent": 220,
  Country: 96,
  Region: 96,
  Attention: 96,
  Assigned: 140,
  "Visitor since": 148,
  "Chat started": 148,
  "Last message": 148,
  Closed: 148,
  Transcript: 124,
  Block: 100,
}

export const WIDTHS_KEY = "supportchat.data.column-widths"
export const MIN_COLUMN_WIDTH = 80
export const MAX_COLUMN_WIDTH = 720
export const WIDTH_STEP = 24

export const clampWidth = (value: number) => {
  return Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, Math.round(value)))
}

export const readStoredWidths = (): Record<ColumnLabel, number> => {
  if (typeof window === "undefined") {
    return DEFAULT_WIDTHS
  }
  try {
    const raw = window.localStorage.getItem(WIDTHS_KEY)
    if (!raw) {
      return DEFAULT_WIDTHS
    }
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const next = { ...DEFAULT_WIDTHS }
    for (const label of COLUMNS) {
      const value = parsed[label]
      if (typeof value === "number" && Number.isFinite(value)) {
        next[label] = clampWidth(value)
      }
    }
    return next
  } catch {
    return DEFAULT_WIDTHS
  }
}

export const blank = (value: string | null | undefined) => {
  const trimmed = value?.trim()
  if (!trimmed) {
    return "—"
  }
  return trimmed
}

export const formatWhen = (value: string | null | undefined) => {
  if (!value) {
    return "—"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

export const stateClass = (state: string) => {
  if (state === "closed") {
    return "bg-ice-2 text-mute"
  }
  if (state === "queued") {
    return "bg-ember/10 text-ember"
  }
  if (state === "human") {
    return "bg-steel/10 text-steel"
  }
  return "bg-navy/10 text-navy"
}
