"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop -- Row and filter items are short, per-item motion props that a shared component would not simplify. */

import { Inbox as InboxIcon, Search } from "lucide-react"
import { motion } from "motion/react"
import { useCallback, useMemo, useState, type ChangeEvent } from "react"

import { Input } from "@/components/ui/input"

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
    return "bg-[#29915E]"
  }
  if (state === "bot") {
    return "bg-steel"
  }
  return "bg-mute/50"
}

const stateChipClass = (state: string) => {
  const base =
    "mt-1.5 flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase"
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
  "bg-[#29915E]/15 text-[#1F7048]",
  "bg-navy/10 text-navy",
]

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
      <motion.button
        type="button"
        layout="position"
        onClick={handleSelect}
        aria-current={selected ? "true" : undefined}
        whileTap={{ scale: 0.99 }}
        className={`relative flex w-full items-start gap-3 rounded-[12px] px-3 py-3 text-left transition-colors duration-150 ease-out ${
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
      </motion.button>
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
  const handleLoadMoreClick = useCallback(() => {
    if (nextCursor) {
      onLoadMore(nextCursor)
    }
  }, [nextCursor, onLoadMore])
  const handleSearch = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value)
  }, [])
  const visibleItems = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) {
      return items
    }
    return items.filter((item) =>
      `${item.visitor_display} ${item.site_name} ${item.preview}`
        .toLowerCase()
        .includes(normalized),
    )
  }, [items, query])
  return (
    <section className="border-line bg-paper flex min-h-0 w-full flex-col border-r lg:w-[420px] lg:shrink-0">
      <div className="border-line flex h-16 items-center justify-between border-b px-5">
        <h2 className="text-navy text-sm font-extrabold tracking-[-0.02em]">Conversations</h2>
        <span
          className="bg-ice-2 text-mute inline-flex shrink-0 items-center rounded-full px-2 py-1 font-mono text-[10px] font-bold"
          aria-label={`${items.length} conversations`}
        >
          {items.length}
        </span>
      </div>
      <label htmlFor="conversation-search" className="relative mx-4 mt-4 mb-3 block">
        <span className="sr-only">Search chats</span>
        <Search aria-hidden="true" className="text-mute absolute top-2.5 left-3 size-4" />
        <Input
          id="conversation-search"
          name="query"
          autoComplete="off"
          type="search"
          value={query}
          onChange={handleSearch}
          placeholder="Search chat"
          className="border-line bg-ice-2/60 text-ink placeholder:text-mute focus-visible:ring-steel dark:bg-ice-2/60 h-10 rounded-full border pr-3 pl-9 text-sm outline-none focus-visible:ring-2"
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
}: {
  item: (typeof INBOX_FILTERS)[number]
  active: boolean
  count: number
  onFilter: (filter: InboxFilter) => void
}) => {
  const handleClick = useCallback(() => onFilter(item.id), [item.id, onFilter])
  return (
    <button
      type="button"
      aria-label={item.label}
      aria-pressed={active}
      onClick={handleClick}
      className={`relative flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-full px-2.5 text-center text-[11px] font-bold whitespace-nowrap transition-colors duration-150 ${
        active ? "text-navy" : "text-mute hover:text-ink"
      }`}
    >
      {active ? (
        <motion.span
          layoutId="inbox-filter-active"
          transition={{ type: "spring", stiffness: 500, damping: 42 }}
          className="bg-paper absolute inset-0 rounded-full shadow-[0_1px_4px_rgba(13,31,58,0.08)]"
        />
      ) : null}
      <span className={`relative size-1.5 shrink-0 rounded-full ${stateDotClass(item.id)}`} />
      <span className="relative">{item.label}</span>
      <span className="text-mute relative shrink-0 font-mono text-[10px]">{count}</span>
    </button>
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
  return (
    <nav
      aria-label="Inbox filters"
      className="border-line bg-ice-2/50 mx-4 mb-3 flex h-9 flex-nowrap items-center gap-1 rounded-full border p-1"
    >
      {INBOX_FILTERS.map((item) => (
        <InboxFilterButton
          key={item.id}
          item={item}
          active={filter === item.id}
          count={counts[item.id]}
          onFilter={onFilter}
        />
      ))}
    </nav>
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
  return (
    <ul aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto">
      {items.length === 0 ? (
        <li className="px-5 py-10 text-center">
          <InboxIcon
            aria-hidden="true"
            className="text-mute/50 mx-auto mb-2 size-6"
            strokeWidth={1.5}
          />
          <p className="text-ink text-sm font-bold">{query ? "No chats found" : "Inbox clear"}</p>
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
          <button
            type="button"
            onClick={onLoadMore}
            className="text-steel hover:text-navy w-full rounded-[6px] px-2 py-2 text-sm font-semibold transition-[color,transform] duration-150 ease-out hover:-translate-y-px"
          >
            Load more
          </button>
        </li>
      ) : null}
    </ul>
  )
}
