import { type SiteRecord } from "@/components/admin/staff-api"

export type CannedReplyRecord = {
  id: string
  site_id: string | null
  shortcut: string
  body: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type Scope = string
export type StatusFilter = "all" | "enabled" | "disabled"
export type FormState = {
  id: string | null
  siteId: string | null
  shortcut: string
  body: string
  enabled: boolean
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
