"use client"
/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-function-as-prop -- Each Base UI option links to its own destination. */
import { Autocomplete } from "@base-ui/react/autocomplete"
import {
  ArrowUpRight,
  CornerDownLeft,
  MessageSquare,
  Globe,
  BookOpen,
  FileText,
  ShieldBan,
  Activity,
  Bell,
  Settings,
} from "lucide-react"

import { Separator } from "@/components/ui/separator"

import { screenLabel, type SearchItem } from "./search-destinations"
import type { SearchController } from "./use-search-controller"
const resultIcons = {
  inbox: MessageSquare,
  data: FileText,
  sites: Globe,
  knowledge: BookOpen,
  "canned-responses": MessageSquare,
  "suggested-faqs": BookOpen,
  blocked: ShieldBan,
  logs: FileText,
  status: Activity,
  notifications: Bell,
  settings: Settings,
}
const ResultIcon = ({ item }: { item: SearchItem }) => {
  const Icon = item.kind === "navigation" ? ArrowUpRight : resultIcons[item.screen]
  return <Icon className="size-4" aria-hidden="true" />
}

const Highlight = ({ text, query }: { text: string; query: string }) => {
  const terms = query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
  if (!terms.length) return text
  const regex = new RegExp(`(${terms.join("|")})`, "gi")
  let offset = 0
  return text.split(regex).map((part, index) => {
    const start = offset
    offset += part.length
    return index % 2 ? (
      <mark key={start} className="bg-steel/10 rounded-sm font-semibold text-inherit">
        {part}
      </mark>
    ) : (
      part
    )
  })
}

const SearchOption = ({ item, state }: { item: SearchItem; state: SearchController }) => (
  <Autocomplete.Item
    value={item}
    render={<a href={item.href} aria-label={item.title} />}
    onClick={(event) => state.navigate(item, event)}
    className="group text-ink data-highlighted:bg-ice-2 flex cursor-pointer items-center gap-3 rounded-xl px-3 py-3 outline-none"
  >
    <span className="border-line bg-paper text-steel flex size-9 shrink-0 items-center justify-center rounded-lg border">
      <ResultIcon item={item} />
    </span>
    <span className="min-w-0 flex-1">
      <span className="block truncate text-sm font-medium">
        <Highlight text={item.title} query={state.query} />
      </span>
      <span className="text-mute mt-0.5 line-clamp-2 text-xs leading-5">
        <Highlight text={item.description} query={state.query} />
      </span>
    </span>
    <span className="text-mute hidden shrink-0 text-[10px] sm:block">
      {screenLabel(item.screen)}
    </span>
    <CornerDownLeft
      className="text-mute hidden size-3.5 shrink-0 opacity-0 group-data-highlighted:opacity-100 sm:block"
      aria-hidden="true"
    />
  </Autocomplete.Item>
)

export const SearchResultsList = ({ state }: { state: SearchController }) => (
  <Autocomplete.List
    className="min-h-0 overflow-y-auto overscroll-contain p-2"
    aria-label="Workspace results"
    aria-busy={state.loading}
  >
    {state.groups.map((group, index) => (
      <Autocomplete.Group key={group.label}>
        {group.items.length > 0 || (index === 0 && state.searchable) ? (
          <Autocomplete.GroupLabel className="text-mute flex items-center gap-3 px-3 pt-3 pb-1.5 text-[10px] font-semibold tracking-wider uppercase">
            <span className="shrink-0">{group.label}</span>
            {index === 2 ? <Separator className="w-auto flex-1 opacity-70" /> : null}
          </Autocomplete.GroupLabel>
        ) : null}
        {index === 0 && state.searchable && group.items.length === 0 ? (
          <p className="text-mute px-3 py-3 text-sm">
            {state.loading
              ? "Finding matching records…"
              : state.failed
                ? "Record search is unavailable."
                : "No matches in this screen."}
          </p>
        ) : null}
        {group.items.map((item) => (
          <SearchOption key={item.id} item={item} state={state} />
        ))}
      </Autocomplete.Group>
    ))}
    {!state.searchable ? (
      <p className="text-mute px-3 py-3 text-xs">
        Find a chat, contact, website, answer, or setting. Try “SampleSite site settings”.
      </p>
    ) : null}
    {!state.loading && state.searchable && !state.failed && state.items.length === 0 ? (
      <p className="text-mute px-3 py-4 text-sm">
        No matches across the workspace. Try a name, email, shortcut, or fewer words.
      </p>
    ) : null}
  </Autocomplete.List>
)
