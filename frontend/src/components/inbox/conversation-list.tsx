"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop -- Row and filter items are short, per-item motion props that a shared component would not simplify. */

import { cn } from "cn"
import { Inbox as InboxIcon, Search } from "lucide-react"
import { LayoutGroup, motion, useReducedMotion } from "motion/react"
import { useCallback, useDeferredValue, useMemo, useState, type ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { linkUnderlineClass } from "@/components/ui/link-button"
import { matchesSearchQuery } from "@/lib/search"

import { INBOX_FILTERS, type InboxCounts, type InboxFilter, type InboxListItem } from "./types"

type ConversationListProps = {
  filter: InboxFilter
  items: InboxListItem[]
  selectedId: string | null
  nextCursor: string | null
  counts: InboxCounts
  onFilter: (filter: InboxFilter) => void
  onSelect: (id: string) => void
  onLoadMore: (cursor: string) => void
}

const stateLabel = (state: string) => {
  if (state === "human") {
    return "Live"
  }
  if (state === "bot") {
    return "Assistant"
  }
  if (state === "queued") {
    return "Needs Attention"
  }
  if (state === "closed") {
    return "Closed"
  }
  return state
}

const stateDotClass = (state: string) => {
  if (state === "queued") {
    return "bg-ember"
  }
  if (state === "human") {
    return "bg-steel"
  }
  if (state === "bot") {
    return "bg-steel"
  }
  return "bg-mute/50"
}

const stateChipClass = (state: string) => {
  const base =
    "mt-1.5 flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase"
  if (state === "queued") {
    return `${base} bg-ember/10 text-ember`
  }
  if (state === "human") {
    return `${base} bg-navy text-white dark:text-navy-deep`
  }
  if (state === "bot") {
    return `${base} bg-ice text-steel`
  }
  return `${base} text-mute bg-ice-2`
}

const avatarPalette = [
  "bg-steel/15 text-steel",
  "bg-ember/15 text-ember",
  "bg-steel/15 text-steel",
  "bg-navy/10 text-navy",
]

const MotionButton = motion.create(Button)

const FILTER_SLIDER_SPRING = {
  type: "spring",
  stiffness: 380,
  damping: 34,
  mass: 0.7,
} as const

const FILTER_SLIDER_INSTANT = { duration: 0 } as const

const avatarClassFor = (seed: string) => {
  let hash = 0
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash + seed.charCodeAt(index)) % avatarPalette.length
  }
  return avatarPalette[hash]
}

const initialFor = (name: string) => name.trim().slice(0, 1).toUpperCase() || "?"

const formatTime = (iso: string) => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

type RowProps = {
  item: InboxListItem
  selected: boolean
  onSelect: (id: string) => void
}

const ConversationRow = ({ item, selected, onSelect }: RowProps) => {
  const handleSelect = useCallback(() => onSelect(item.id), [item.id, onSelect])
  return (
    <li className="border-line border-b px-2 py-1 last:border-b-0">
      <MotionButton
        type="button"
        variant="ghost"
        layout="position"
        onClick={handleSelect}
        aria-current={selected ? "true" : undefined}
        whileTap={{ scale: 0.99 }}
        className={`relative flex h-auto w-full items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors duration-150 ease-out ${
          selected ? "bg-ice-2" : "hover:bg-ice-2/70"
        }`}
      >
        {selected ? (
          <motion.span
            layoutId="conversation-active-rail"
            transition={{ type: "spring", stiffness: 500, damping: 42 }}
            aria-hidden="true"
            className="bg-ember absolute top-2 bottom-2 left-0 w-0.5 rounded-full"
          />
        ) : null}
        <span
          aria-hidden="true"
          className={`flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-bold ${avatarClassFor(item.visitor_display)}`}
        >
          {initialFor(item.visitor_display)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span className="text-ink truncate text-sm font-semibold">{item.visitor_display}</span>
            <time
              dateTime={item.last_message_at}
              className="text-mute shrink-0 font-mono text-[10px]"
            >
              {formatTime(item.last_message_at)}
            </time>
          </span>
          <span className="text-mute block truncate text-[11px]">{item.site_name}</span>
          <span className="text-ink line-clamp-2 text-xs leading-5">{item.preview}</span>
          <span aria-hidden="true" className={stateChipClass(item.state)}>
            <span className={`size-1.5 rounded-full ${stateDotClass(item.state)}`} />
            {stateLabel(item.state)}
          </span>
        </span>
      </MotionButton>
    </li>
  )
}

export const ConversationList = ({
  filter,
  items,
  selectedId,
  nextCursor,
  counts,
  onFilter,
  onSelect,
  onLoadMore,
}: ConversationListProps) => {
  const [query, setQuery] = useState("")
  const deferredQuery = useDeferredValue(query)
  const handleLoadMoreClick = useCallback(() => {
    if (nextCursor) {
      onLoadMore(nextCursor)
    }
  }, [nextCursor, onLoadMore])
  const handleSearch = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value)
  }, [])
  const visibleItems = useMemo(() => {
    return items.filter((item) =>
      matchesSearchQuery(
        [item.visitor_display, item.site_name, item.preview, stateLabel(item.state)],
        deferredQuery,
      ),
    )
  }, [deferredQuery, items])
  return (
    <section className="border-line bg-paper flex min-h-0 w-full flex-col border-r lg:w-[420px] lg:shrink-0">
      <div className="border-line flex h-16 items-center border-b px-5">
        <h2 className="text-navy heading text-sm">Conversations</h2>
      </div>
      <label htmlFor="conversation-search" className="relative mx-4 mt-4 mb-3 block">
        <span className="sr-only">Search chats</span>
        <Search aria-hidden="true" className="text-mute absolute top-2.5 left-3 size-4" />
        <Input
          id="conversation-search"
          name="query"
          autoComplete="off"
          spellCheck={false}
          type="search"
          value={query}
          onChange={handleSearch}
          placeholder="Search conversations"
          className="border-line bg-ice-2/60 text-ink placeholder:text-mute focus-visible:ring-steel dark:bg-ice-2/60 h-10 rounded-lg border pr-3 pl-9 text-sm outline-none focus-visible:ring-2"
        />
      </label>
      <InboxFilterNav filter={filter} counts={counts} onFilter={onFilter} />
      <ConversationRows
        items={visibleItems}
        selectedId={selectedId}
        nextCursor={nextCursor}
        query={query}
        onSelect={onSelect}
        onLoadMore={handleLoadMoreClick}
      />
    </section>
  )
}

const InboxFilterButton = ({
  item,
  active,
  count,
  onFilter,
  sliderTransition,
}: {
  item: (typeof INBOX_FILTERS)[number]
  active: boolean
  count: number
  onFilter: (filter: InboxFilter) => void
  sliderTransition: typeof FILTER_SLIDER_SPRING | typeof FILTER_SLIDER_INSTANT
}) => {
  const handleClick = useCallback(() => onFilter(item.id), [item.id, onFilter])
  return (
    <Button
      type="button"
      variant="ghost"
      aria-label={item.label}
      aria-pressed={active}
      onClick={handleClick}
      className={`relative flex h-8 shrink-0 items-center justify-center gap-1 rounded-full px-2 text-center text-[11px] leading-none font-bold whitespace-nowrap transition-colors duration-200 ease-out ${
        active ? "text-navy" : "text-mute hover:text-ink"
      }`}
    >
      {active ? (
        <motion.span
          layoutId="inbox-filter-active"
          transition={sliderTransition}
          aria-hidden="true"
          className="bg-paper absolute inset-0 rounded-full shadow-[0_1px_3px_rgba(13,31,58,0.10),0_0_0_1px_rgba(13,31,58,0.04)]"
        />
      ) : null}
      <span className={`relative size-1.5 shrink-0 rounded-full ${stateDotClass(item.id)}`} />
      <span className="relative">
        {item.label}
        <span className="text-mute font-mono text-[10px] tabular-nums"> {count}</span>
      </span>
    </Button>
  )
}

const InboxFilterNav = ({
  filter,
  counts,
  onFilter,
}: {
  filter: InboxFilter
  counts: InboxCounts
  onFilter: (filter: InboxFilter) => void
}) => {
  const reducedMotion = useReducedMotion()
  const sliderTransition = reducedMotion ? FILTER_SLIDER_INSTANT : FILTER_SLIDER_SPRING
  return (
    <LayoutGroup id="inbox-filters">
      <nav
        aria-label="Inbox filters"
        className="border-line bg-ice-2/70 mx-4 mb-3 flex h-10 flex-nowrap items-center justify-between gap-0.5 overflow-visible rounded-full border p-1"
      >
        {INBOX_FILTERS.map((item) => (
          <InboxFilterButton
            key={item.id}
            item={item}
            active={filter === item.id}
            count={counts[item.id]}
            onFilter={onFilter}
            sliderTransition={sliderTransition}
          />
        ))}
      </nav>
    </LayoutGroup>
  )
}

type RowsProps = {
  items: InboxListItem[]
  selectedId: string | null
  nextCursor: string | null
  query: string
  onSelect: (id: string) => void
  onLoadMore: () => void
}

const ConversationRows = ({
  items,
  selectedId,
  nextCursor,
  query,
  onSelect,
  onLoadMore,
}: RowsProps) => {
  const isEmpty = items.length === 0
  return (
    <ul
      aria-label="Conversations"
      className={cn("min-h-0 flex-1 overflow-y-auto", isEmpty && "flex flex-col justify-center")}
    >
      {isEmpty ? (
        <li className="px-5 text-center">
          <InboxIcon
            aria-hidden="true"
            className="text-mute/50 mx-auto mb-2 size-6"
            strokeWidth={1.5}
          />
          <p className="text-ink heading text-sm">
            {query ? `No chats match “${query.trim()}”` : "Inbox clear"}
          </p>
          <p className="text-mute mt-1 text-xs leading-5">
            {query
              ? "Try a visitor name, site, or phrase."
              : "New conversations will appear here when a visitor needs help."}
          </p>
        </li>
      ) : null}
      {items.map((item) => (
        <ConversationRow
          key={item.id}
          item={item}
          selected={selectedId === item.id}
          onSelect={onSelect}
        />
      ))}
      {nextCursor ? (
        <li className="p-3">
          <Button
            type="button"
            variant="link"
            onClick={onLoadMore}
            className={cn(
              linkUnderlineClass,
              "text-steel hover:text-navy inline-flex text-sm font-semibold transition-colors duration-150 ease-out",
            )}
          >
            Load more
          </Button>
        </li>
      ) : null}
    </ul>
  )
}
