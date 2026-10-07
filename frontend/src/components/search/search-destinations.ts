import { matchesSearchQuery } from "@/lib/search"

export type SearchScreen =
  | "inbox"
  | "data"
  | "sites"
  | "knowledge"
  | "canned-responses"
  | "suggested-faqs"
  | "blocked"
  | "logs"
  | "status"
  | "notifications"
  | "settings"
export type SearchItem = {
  id: string
  screen: SearchScreen
  title: string
  description: string
  href: string
  kind: string
}
export type SearchResults = { current: SearchItem[]; navigation: SearchItem[]; other: SearchItem[] }
const destinations: [SearchScreen, string, string][] = [
  ["inbox", "Inbox", "chats conversations live bot needs attention"],
  ["data", "Data", "submissions forms contacts export"],
  ["sites", "Sites", "websites site settings widget"],
  ["knowledge", "Knowledge base", "sources pages articles documents"],
  ["canned-responses", "Canned responses", "replies shortcuts"],
  ["suggested-faqs", "Suggested FAQs", "gaps unanswered questions"],
  ["blocked", "Blocked visitors", "unblock"],
  ["logs", "Logs", "errors diagnostics"],
  [
    "status",
    "Status",
    "health services uptime redis postgres database api worker latency incidents",
  ],
  ["notifications", "Notification settings", "push sound alerts preferences"],
  ["settings", "Account settings", "profile password theme appearance"],
]
export const searchScreen = (pathname: string): SearchScreen =>
  destinations.find(([key]) => pathname === `/admin/${key}`)?.[0] ?? "inbox"
export const screenLabel = (screen: SearchScreen) =>
  destinations.find(([key]) => key === screen)?.[1] ?? "Workspace"
export const navigationMatches = (query: string, isAdmin: boolean): SearchItem[] =>
  destinations
    .filter(
      ([key, title, aliases]) =>
        (isAdmin || key !== "logs") && matchesSearchQuery([title, aliases], query),
    )
    .map(([screen, title]) => ({
      id: `nav:${screen}`,
      screen,
      title,
      description: "Open workspace view",
      href: `/admin/${screen}`,
      kind: "navigation",
    }))

const isSearchItem = (value: unknown): value is SearchItem => {
  if (value === null || typeof value !== "object") return false
  const item = value as Record<string, unknown>
  if (
    !["id", "title", "description", "href", "kind", "screen"].every(
      (field) => typeof item[field] === "string",
    )
  )
    return false
  const destination = destinations.find(([screen]) => item.screen === screen)
  return Boolean(
    destination &&
    (item.href === `/admin/${destination[0]}` ||
      String(item.href).startsWith(`/admin/${destination[0]}?`)),
  )
}
export const isSearchResults = (value: unknown): value is SearchResults => {
  if (value === null || typeof value !== "object") return false
  const results = value as Record<string, unknown>
  return ["current", "navigation", "other"].every(
    (key) =>
      Array.isArray(results[key]) && results[key].length <= 12 && results[key].every(isSearchItem),
  )
}
