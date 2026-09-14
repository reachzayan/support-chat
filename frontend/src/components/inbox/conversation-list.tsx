"use client"

import { Search } from "lucide-react"
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

const stateChipClass = (state: string) => {
  const base = "mt-1 w-fit rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase"
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
    <li className="border-line/60 border-b last:border-b-0">
      <button
        type="button"
        onClick={handleSelect}
        aria-current={selected ? "true" : undefined}
        className={`flex w-full flex-col gap-1 px-3 py-3 text-left ${
          selected
            ? "border-ember bg-navy-mid border-l-2"
            : "hover:bg-ice-2 bg-paper border-l-2 border-transparent"
        }`}
      >
        <span className="flex items-baseline justify-between gap-2">
          <span className="text-ink truncate text-sm font-semibold">{item.visitor_display}</span>
          <time
            dateTime={item.last_message_at}
            className="text-mute shrink-0 font-mono text-[11px]"
          >
            {formatTime(item.last_message_at)}
          </time>
        </span>
        <span className="text-mute text-xs">{item.site_name}</span>
        <span className="text-ink line-clamp-2 text-xs leading-5">{item.preview}</span>
        <span aria-hidden="true" className={stateChipClass(item.state)}>
          {stateLabel(item.state)}
        </span>
      </button>
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
    <section className="border-line/70 bg-paper flex min-h-0 w-full flex-col border-r lg:w-[300px] lg:shrink-0">
      <div className="border-line/70 flex items-center justify-between border-b px-5 py-4">
        <h2 className="text-navy text-sm font-extrabold tracking-[-0.02em]">Conversations</h2>
        <span
          className="bg-ice-2 text-mute rounded-full px-2 py-1 font-mono text-[10px]"
          aria-label={`${items.length} conversations`}
        >
          {items.length}
        </span>
      </div>
      <label
        htmlFor="conversation-search"
        className="border-line/70 relative mx-4 mt-4 block border-b pb-4"
      >
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
          className="border-line bg-ice text-ink placeholder:text-mute focus-visible:ring-steel dark:bg-ice h-10 rounded-[10px] border pr-3 pl-9 text-sm outline-none focus-visible:ring-2"
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
      className={`flex min-h-10 w-full items-center justify-between rounded-[8px] px-3 text-left text-xs font-bold ${
        active ? "bg-navy-mid text-navy" : "text-mute hover:bg-ice-2 hover:text-ink"
      }`}
    >
      <span className="flex items-center gap-2">
        <span
          className={`size-2 ${item.id === "human" ? "bg-[#29915E]" : item.id === "queued" ? "bg-ember" : item.id === "bot" ? "bg-steel" : "bg-mute/50"} rounded-full`}
        />
        {item.label}
      </span>
      <span className="font-mono text-[10px]">{count}</span>
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
    <nav aria-label="Inbox filters" className="border-line/70 border-b px-4 py-4">
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
            className="text-steel hover:text-navy w-full rounded-[6px] px-2 py-2 text-sm font-semibold"
          >
            Load more
          </button>
        </li>
      ) : null}
    </ul>
  )
}
