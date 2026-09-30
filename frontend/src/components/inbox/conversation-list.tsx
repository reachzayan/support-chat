"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-object-as-prop -- Row and filter items are short, per-item motion props that a shared component would not simplify. */

import { cn } from "cn"
import { Inbox as InboxIcon, Search } from "lucide-react"
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react"
import { useCallback, useDeferredValue, useMemo, useState, type ChangeEvent } from "react"

import { ResizableListPane } from "@/components/admin/pane-resize-handle"
import { RetryError } from "@/components/admin/retry-error"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { linkUnderlineClass } from "@/components/ui/link-button"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  INBOX_LIST_DEFAULT_WIDTH,
  INBOX_LIST_WIDTH_KEY,
  MAX_PANE_WIDTH,
  MIN_PANE_WIDTH,
  usePaneWidth,
} from "@/lib/pane-width"
import { matchesSearchQuery } from "@/lib/search"

import {
  INBOX_FILTERS,
  type InboxCounts,
  type InboxFilter,
  type InboxListItem,
  type InboxSite,
} from "./types"

type ConversationListProps = {
  filter: InboxFilter
  siteId: string | null
  sites: InboxSite[]
  items: InboxListItem[]
  selectedId: string | null
  nextCursor: string | null
  counts: InboxCounts
  loadError: boolean
  onFilter: (filter: InboxFilter) => void
  onSite: (siteId: string | null) => void
  onSelect: (id: string) => void
  onLoadMore: (cursor: string) => void
  onRetryLoad: () => void
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
const ROW_RAIL_SPRING = { type: "spring", stiffness: 500, damping: 42 } as const
const ROW_FADE = { duration: 0.16, ease: [0.22, 1, 0.36, 1] } as const
const hiddenChip = { opacity: 0, y: 4 }
const shownChip = { opacity: 1, y: 0 }
const hiddenRow = { opacity: 0, y: 6 }
const shownRow = { opacity: 1, y: 0 }
const exitRow = { opacity: 0, y: -4 }
const exitChip = { opacity: 0, y: -2 }

type SliderTransition = typeof FILTER_SLIDER_SPRING | typeof FILTER_SLIDER_INSTANT

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
  showSite: boolean
  onSelect: (id: string) => void
}

const SiteChip = ({ name, reducedMotion }: { name: string; reducedMotion: boolean }) => (
  <motion.span
    initial={reducedMotion ? false : hiddenChip}
    animate={shownChip}
    exit={reducedMotion ? undefined : exitChip}
    transition={reducedMotion ? FILTER_SLIDER_INSTANT : ROW_FADE}
    className="bg-ice-2 text-mute mt-0.5 inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide"
  >
    {name}
  </motion.span>
)

const ConversationRow = ({ item, selected, showSite, onSelect }: RowProps) => {
  const handleSelect = useCallback(() => onSelect(item.id), [item.id, onSelect])
  const reducedMotion = Boolean(useReducedMotion())
  return (
    <motion.li
      initial={reducedMotion ? false : hiddenRow}
      animate={shownRow}
      exit={reducedMotion ? undefined : exitRow}
      transition={reducedMotion ? FILTER_SLIDER_INSTANT : ROW_FADE}
      className="border-line border-b px-2 py-1 last:border-b-0"
    >
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
            transition={reducedMotion ? FILTER_SLIDER_INSTANT : ROW_RAIL_SPRING}
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
          <AnimatePresence initial={false}>
            {showSite ? (
              <SiteChip key="site-chip" name={item.site_name} reducedMotion={reducedMotion} />
            ) : null}
          </AnimatePresence>
          <span className="text-ink line-clamp-2 text-xs leading-5">{item.preview}</span>
          <span aria-hidden="true" className={stateChipClass(item.state)}>
            <span className={`size-1.5 rounded-full ${stateDotClass(item.state)}`} />
            {stateLabel(item.state)}
          </span>
        </span>
      </MotionButton>
    </motion.li>
  )
}

export const ConversationList = ({
  filter,
  siteId,
  sites,
  items,
  selectedId,
  nextCursor,
  counts,
  loadError,
  onFilter,
  onSite,
  onSelect,
  onLoadMore,
  onRetryLoad,
}: ConversationListProps) => {
  const [query, setQuery] = useState("")
  const deferredQuery = useDeferredValue(query)
  const pane = usePaneWidth(INBOX_LIST_WIDTH_KEY, INBOX_LIST_DEFAULT_WIDTH)
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
    <ResizableListPane
      label="conversation list"
      width={pane.width}
      dragging={pane.dragging}
      min={MIN_PANE_WIDTH}
      max={MAX_PANE_WIDTH}
      className="border-line bg-paper flex min-h-0 w-full min-w-0 flex-col overflow-hidden border-r"
      onResizeStart={pane.handleResizeStart}
      onResizeKeyDown={pane.handleResizeKeyDown}
      onResizeReset={pane.handleResizeReset}
    >
      <ConversationListBody
        filter={filter}
        siteId={siteId}
        sites={sites}
        items={visibleItems}
        selectedId={selectedId}
        nextCursor={nextCursor}
        counts={counts}
        loadError={loadError}
        query={query}
        onFilter={onFilter}
        onSite={onSite}
        onSelect={onSelect}
        onSearch={handleSearch}
        onLoadMore={handleLoadMoreClick}
        onRetryLoad={onRetryLoad}
      />
    </ResizableListPane>
  )
}

const ConversationListBody = ({
  filter,
  siteId,
  sites,
  items,
  selectedId,
  nextCursor,
  counts,
  loadError,
  query,
  onFilter,
  onSite,
  onSelect,
  onSearch,
  onLoadMore,
  onRetryLoad,
}: {
  filter: InboxFilter
  siteId: string | null
  sites: InboxSite[]
  items: InboxListItem[]
  selectedId: string | null
  nextCursor: string | null
  counts: InboxCounts
  loadError: boolean
  query: string
  onFilter: (filter: InboxFilter) => void
  onSite: (siteId: string | null) => void
  onSelect: (id: string) => void
  onSearch: (event: ChangeEvent<HTMLInputElement>) => void
  onLoadMore: () => void
  onRetryLoad: () => void
}) => {
  return (
    <>
      <div className="border-line flex h-16 items-center border-b px-5">
        <h2 className="text-navy heading text-sm">Conversations</h2>
      </div>
      <div className="mx-4 mt-4 mb-3 inline-flex w-fit max-w-full flex-col gap-3 self-start">
        <label htmlFor="conversation-search" className="relative block w-full min-w-0">
          <span className="sr-only">Search chats</span>
          <Search aria-hidden="true" className="text-mute absolute top-2.5 left-3 size-4" />
          <Input
            id="conversation-search"
            name="query"
            autoComplete="off"
            spellCheck={false}
            type="search"
            size={1}
            value={query}
            onChange={onSearch}
            placeholder="Search conversations"
            className="border-line bg-ice-2/60 text-ink placeholder:text-mute focus-visible:ring-steel dark:bg-ice-2/60 h-10 w-full min-w-0 rounded-lg border pr-3 pl-9 text-sm outline-none focus-visible:ring-2"
          />
        </label>
        <InboxSiteNav sites={sites} siteId={siteId} onSite={onSite} />
        <InboxFilterNav filter={filter} counts={counts} onFilter={onFilter} />
      </div>
      {loadError ? (
        <div className="px-4 pb-3">
          <RetryError text="Inbox could not be loaded" onRetry={onRetryLoad} className="mt-0" />
        </div>
      ) : (
        <ConversationRows
          items={items}
          selectedId={selectedId}
          nextCursor={nextCursor}
          query={query}
          showSite={siteId === null}
          onSelect={onSelect}
          onLoadMore={onLoadMore}
        />
      )}
    </>
  )
}

const ALL_INBOXES = "all"

const inboxOptionLabel = (name: string, count: number) => `${name} ${count}`

const queuedElsewhere = (sites: InboxSite[], siteId: string | null) => {
  if (siteId === null) {
    return 0
  }
  return sites.reduce((sum, site) => (site.id === siteId ? sum : sum + site.queued), 0)
}

const orderInboxSites = (sites: InboxSite[]) =>
  [...sites].toSorted((left, right) => {
    if (right.queued !== left.queued) {
      return right.queued - left.queued
    }
    return left.name.localeCompare(right.name)
  })

const inboxSelectItems = (sites: InboxSite[], siteId: string | null, queuedAll: number) => {
  const next: Record<string, string> = {
    [ALL_INBOXES]: inboxOptionLabel("All", queuedAll),
  }
  for (const site of sites) {
    next[site.id] = inboxOptionLabel(site.name, site.queued)
  }
  if (siteId !== null && next[siteId] === undefined) {
    next[siteId] = "Inbox"
  }
  return next
}

const InboxElsewhereBadge = ({ count }: { count: number }) => (
  <span
    aria-label={`${count} needs attention in other inboxes`}
    className="bg-ember text-paper ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-[6px] px-1.5 font-mono text-[10px] font-bold tabular-nums"
  >
    +{count}
  </span>
)

const InboxSiteNav = ({
  sites,
  siteId,
  onSite,
}: {
  sites: InboxSite[]
  siteId: string | null
  onSite: (siteId: string | null) => void
}) => {
  const queuedAll = sites.reduce((sum, site) => sum + site.queued, 0)
  const elsewhere = queuedElsewhere(sites, siteId)
  const orderedSites = useMemo(() => orderInboxSites(sites), [sites])
  const items = useMemo(
    () => inboxSelectItems(sites, siteId, queuedAll),
    [queuedAll, siteId, sites],
  )
  const handleSiteChange = useCallback(
    (value: unknown) => {
      if (typeof value !== "string") {
        return
      }
      onSite(value === ALL_INBOXES ? null : value)
    },
    [onSite],
  )
  const triggerLabel =
    elsewhere > 0 ? `Inbox, ${elsewhere} needs attention in other inboxes` : "Inbox"
  return (
    <div className="min-w-0">
      <Select value={siteId ?? ALL_INBOXES} onValueChange={handleSiteChange} items={items}>
        <SelectTrigger
          aria-label={triggerLabel}
          className="border-line bg-paper text-navy hover:border-navy focus-visible:border-steel focus-visible:ring-steel/40 h-10 w-full min-w-0 rounded-[8px] border px-3 text-sm font-semibold shadow-none data-[size=default]:h-10"
        >
          <SelectValue className="min-w-0 truncate font-semibold" />
          {elsewhere > 0 ? <InboxElsewhereBadge count={elsewhere} /> : null}
        </SelectTrigger>
        <SelectContent
          align="start"
          alignItemWithTrigger={false}
          className="border-line bg-paper text-ink w-max min-w-(--anchor-width) rounded-[8px] border shadow-none ring-1 ring-[rgba(13,31,58,0.12)]"
        >
          <SelectGroup>
            <SelectItem value={ALL_INBOXES}>{inboxOptionLabel("All", queuedAll)}</SelectItem>
            {orderedSites.map((site) => (
              <SelectItem
                key={site.id}
                value={site.id}
                className={site.queued > 0 ? "font-semibold" : undefined}
              >
                {inboxOptionLabel(site.name, site.queued)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
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
  sliderTransition: SliderTransition
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
        className="border-line bg-ice-2/70 flex h-10 w-fit max-w-full [scrollbar-width:none] flex-nowrap items-center gap-0.5 overflow-x-auto rounded-full border p-1"
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
  showSite: boolean
  onSelect: (id: string) => void
  onLoadMore: () => void
}

const ConversationRows = ({
  items,
  selectedId,
  nextCursor,
  query,
  showSite,
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
      <AnimatePresence initial={false}>
        {items.map((item) => (
          <ConversationRow
            key={item.id}
            item={item}
            selected={selectedId === item.id}
            showSite={showSite}
            onSelect={onSelect}
          />
        ))}
      </AnimatePresence>
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
