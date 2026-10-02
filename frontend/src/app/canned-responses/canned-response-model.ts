import { type SiteRecord } from "@/components/admin/staff-api"

export type CannedReplyRecord = {
  id: string
  site_id: string | null
  shortcut: string
  body: string
  enabled: boolean
  aliases: string[]
  external_id: number | null
  suggestion_event: string | null
  bot_eligible: boolean
  follows_id: string | null
  hands_off: boolean
  bot_block_reason: string | null
  created_at: string
  updated_at: string
}

export type Scope = string
export type StatusFilter = "all" | "enabled" | "disabled"
export type BotState = "available" | "staff" | "blocked"
export type BotFilter = "all" | BotState
export type FormState = {
  id: string | null
  siteId: string | null
  shortcut: string
  aliasesText: string
  body: string
  enabled: boolean
  botEligible: boolean
  followsId: string | null
  handsOff: boolean
}

export const BODY_MAX = 20000

export const parseAliasesText = (value: string, primary: string) => {
  const seen = new Set<string>()
  const aliases: string[] = []
  for (const part of value.split(/[\s,]+/)) {
    const token = part.replace(/^#/, "").trim().toLowerCase()
    if (!token || token === primary || seen.has(token)) continue
    seen.add(token)
    aliases.push(token)
  }
  return aliases
}
export const scopeLabel = (scope: Scope, sites: SiteRecord[]) =>
  scope === "general"
    ? "General — all websites"
    : (sites.find((site) => site.id === scope)?.name ?? "")

export const statusClass = (enabled: boolean) =>
  enabled
    ? "bg-[#E8F5EE] text-[#247A4D] dark:bg-[#163627] dark:text-[#8DDEAE]"
    : "bg-ice-2 text-mute dark:bg-white/10 dark:text-white/60"

export const formatDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(value),
  )

export const botState = (record: CannedReplyRecord): BotState => {
  if (!record.bot_eligible) return "staff"
  return record.bot_block_reason ? "blocked" : "available"
}

export const NO_PARENT = "none"

// A script can follow General wording or wording on its own website, never another script of its own.
export const followOptions = (
  records: CannedReplyRecord[],
  siteId: string | null,
  ownId: string | null,
) => [
  { value: NO_PARENT, label: "Any time" },
  ...records
    .filter((row) => row.id !== ownId && (row.site_id === null || row.site_id === siteId))
    .map((row) => ({ value: row.id, label: `#${row.shortcut}` })),
]

export const followsLabel = (record: CannedReplyRecord, records: CannedReplyRecord[]) => {
  const parent = records.find((row) => row.id === record.follows_id)
  return parent ? `Only after #${parent.shortcut}` : null
}
