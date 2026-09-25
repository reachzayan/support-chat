"use client"

import { ArrowDown, ArrowUp } from "lucide-react"
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

import { useDataColumnWidths } from "./data-column-widths"
import { DataFilterBar } from "./data-filters"
import {
  EMPTY_FILTERS,
  filterSubmissions,
  isSortableColumn,
  nextColumnSort,
  sortSubmissions,
  type DataFilters,
  type DataSort,
} from "./data-query"
import {
  blank,
  COLUMNS,
  formatWhen,
  STATE_LABEL,
  stateClass,
  type ColumnLabel,
  type SubmissionRow,
} from "./data-shared"

const DataColumnHeader = ({
  label,
  sort,
  onSort,
  onResizeStart,
  onResizeMove,
  onResizeEnd,
  onResizeKeyDown,
  onResizeReset,
}: {
  label: ColumnLabel
  sort: DataSort | null
  onSort: (label: ColumnLabel) => void
  onResizeStart: (label: ColumnLabel, event: React.PointerEvent<HTMLButtonElement>) => void
  onResizeMove: (event: React.PointerEvent<HTMLButtonElement>) => void
  onResizeEnd: () => void
  onResizeKeyDown: (label: ColumnLabel, event: React.KeyboardEvent<HTMLButtonElement>) => void
  onResizeReset: (label: ColumnLabel) => void
}) => {
  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => onResizeStart(label, event),
    [label, onResizeStart],
  )
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>) => onResizeKeyDown(label, event),
    [label, onResizeKeyDown],
  )
  const handleReset = useCallback(() => onResizeReset(label), [label, onResizeReset])
  const handleSort = useCallback(() => onSort(label), [label, onSort])
  const sortable = isSortableColumn(label)
  const active = sort?.column === label
  const ariaSort = active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"

  return (
    <TableHead
      scope="col"
      aria-sort={sortable ? ariaSort : undefined}
      className="text-ink bg-ice-2 sticky top-0 z-10 px-4 py-3 text-[10px] font-semibold tracking-[0.12em] uppercase"
    >
      {sortable ? (
        <Button
          type="button"
          variant="ghost"
          aria-label={`Sort by ${label}`}
          onClick={handleSort}
          className="text-ink hover:bg-ice -ml-2 h-7 min-w-0 justify-start gap-1 px-2 text-[10px] font-semibold tracking-[0.12em] uppercase"
        >
          <span className="truncate">{label}</span>
          <SortIndicator active={active} direction={sort?.direction} />
        </Button>
      ) : (
        <span className="pr-2">{label}</span>
      )}
      <Button
        type="button"
        variant="ghost"
        aria-label={`Resize ${label} column`}
        title="Drag to resize. Arrow keys adjust. Double-click resets."
        onPointerDown={handlePointerDown}
        onPointerMove={onResizeMove}
        onPointerUp={onResizeEnd}
        onPointerCancel={onResizeEnd}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleReset}
        className="group focus-visible:ring-steel absolute top-0 right-0 h-full w-2.5 cursor-col-resize border-0 bg-transparent p-0 focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="bg-line group-hover:bg-steel group-focus-visible:bg-steel absolute top-2 right-0 bottom-2 w-px" />
      </Button>
    </TableHead>
  )
}

const SortIndicator = ({
  active,
  direction,
}: {
  active: boolean
  direction: DataSort["direction"] | undefined
}) => (
  <span className="inline-flex shrink-0 flex-col" aria-hidden="true">
    <ArrowUp
      className={cn("size-2.5", active && direction === "asc" ? "text-ember" : "text-mute/35")}
      strokeWidth={2.6}
    />
    <ArrowDown
      className={cn(
        "-mt-0.5 size-2.5",
        active && direction === "desc" ? "text-ember" : "text-mute/35",
      )}
      strokeWidth={2.6}
    />
  </span>
)

const SubmissionRowView = ({
  row,
  onTranscript,
}: {
  row: SubmissionRow
  onTranscript: (id: string) => void
}) => {
  const handleClick = useCallback(() => onTranscript(row.id), [onTranscript, row.id])
  return (
    <TableRow className="odd:bg-paper even:bg-ice-2/60">
      <Cell>{blank(row.visitor.name)}</Cell>
      <Cell>{blank(row.visitor.email)}</Cell>
      <Cell>{blank(row.visitor.phone)}</Cell>
      <Cell>{blank(row.inquiry_type)}</Cell>
      <Cell>{blank(row.intent)}</Cell>
      <TableCell className="px-4 py-3">
        <Badge className={stateClass(row.state)}>{STATE_LABEL[row.state] ?? row.state}</Badge>
      </TableCell>
      <Cell>{row.site_name}</Cell>
      <Cell mono>{row.site_key}</Cell>
      <Cell>{blank(row.opening_message)}</Cell>
      <Cell>{blank(row.page.title)}</Cell>
      <Cell>{blank(row.page.url)}</Cell>
      <Cell>{blank(row.page.referrer)}</Cell>
      <Cell mono>{blank(row.visitor.ip)}</Cell>
      <Cell>{blank(row.visitor.location)}</Cell>
      <Cell>{blank(row.visitor.user_agent)}</Cell>
      <Cell>{blank(row.visitor.geo_country)}</Cell>
      <Cell>{blank(row.visitor.geo_region)}</Cell>
      <Cell>{row.attention_needed ? "Yes" : "—"}</Cell>
      <Cell>{blank(row.assigned_agent?.display_name)}</Cell>
      <Cell>{formatWhen(row.visitor.created_at)}</Cell>
      <Cell>{formatWhen(row.created_at)}</Cell>
      <Cell>{formatWhen(row.last_message_at)}</Cell>
      <Cell>{formatWhen(row.closed_at)}</Cell>
      <TableCell className="px-4 py-3">
        <Button
          type="button"
          variant="ghost"
          onClick={handleClick}
          aria-label={`Transcript for ${blank(row.visitor.name)}`}
          className="border-line text-navy hover:bg-ice focus-visible:ring-steel cursor-pointer border px-3 py-1.5 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
        >
          Transcript
        </Button>
      </TableCell>
    </TableRow>
  )
}

const Cell = ({ children, mono = false }: { children: string; mono?: boolean }) => (
  <TableCell
    title={children === "—" ? undefined : children}
    className={`text-ink overflow-hidden px-4 py-3 text-xs wrap-break-word ${mono ? "font-mono" : ""}`}
  >
    {children}
  </TableCell>
)

export const SubmissionsTable = ({
  rows,
  hasMore,
  loadMoreError,
  loadingMore,
  onLoadMore,
  onTranscript,
}: {
  rows: SubmissionRow[]
  hasMore: boolean
  loadMoreError: boolean
  loadingMore: boolean
  onLoadMore: () => void
  onTranscript: (id: string) => void
}) => {
  const [filters, setFilters] = useState<DataFilters>(EMPTY_FILTERS)
  const [sort, setSort] = useState<DataSort | null>(null)
  const deferredSearch = useDeferredValue(filters.search)
  const widthsApi = useDataColumnWidths()
  const tableStyle = useMemo(
    () => ({ width: "100%", minWidth: widthsApi.tableWidth }),
    [widthsApi.tableWidth],
  )
  const colStyles = useMemo(
    () => COLUMNS.map((label) => ({ key: label, style: { width: widthsApi.widths[label] } })),
    [widthsApi.widths],
  )
  const visibleAll = useMemo(
    () =>
      sortSubmissions(
        filterSubmissions(rows, {
          search: deferredSearch,
          siteId: filters.siteId,
          intent: filters.intent,
          state: filters.state,
        }),
        sort,
      ),
    [deferredSearch, filters.intent, filters.siteId, filters.state, rows, sort],
  )
  const handleFilters = useCallback((next: DataFilters) => setFilters(next), [])
  const handleSort = useCallback((label: ColumnLabel) => {
    setSort((current) => nextColumnSort(current, label))
  }, [])
  const search = filters.search.trim()
  const emptyMessage = search
    ? `No submissions match “${search}”. Try fewer words or clear the filters.`
    : "No submissions match these filters. Clear a filter to see more results."

  return (
    <section
      aria-label="Form submissions"
      className="border-line bg-paper flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border"
    >
      <div className="border-line flex shrink-0 flex-col gap-4 border-b px-5 py-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-navy heading text-sm">Submissions</h2>
          <p className="text-mute text-xs">
            {visibleAll.length} of {rows.length} loaded
          </p>
        </div>
        <DataFilterBar rows={rows} filters={filters} onFilters={handleFilters} />
      </div>
      <SubmissionsTableGrid
        tableStyle={tableStyle}
        colStyles={colStyles}
        widthsApi={widthsApi}
        visibleRows={visibleAll}
        empty={visibleAll.length === 0}
        emptyMessage={emptyMessage}
        sort={sort}
        hasMore={hasMore}
        loadMoreError={loadMoreError}
        loadingMore={loadingMore}
        onSort={handleSort}
        onLoadMore={onLoadMore}
        onTranscript={onTranscript}
      />
    </section>
  )
}

type SubmissionsTableGridProps = {
  tableStyle: CSSProperties
  colStyles: { key: string; style: CSSProperties }[]
  widthsApi: ReturnType<typeof useDataColumnWidths>
  visibleRows: SubmissionRow[]
  empty: boolean
  emptyMessage: string
  sort: DataSort | null
  hasMore: boolean
  loadMoreError: boolean
  loadingMore: boolean
  onSort: (label: ColumnLabel) => void
  onLoadMore: () => void
  onTranscript: (id: string) => void
}

const SubmissionsTableGrid = ({
  tableStyle,
  colStyles,
  widthsApi,
  visibleRows,
  empty,
  emptyMessage,
  sort,
  hasMore,
  loadMoreError,
  loadingMore,
  onSort,
  onLoadMore,
  onTranscript,
}: SubmissionsTableGridProps) => {
  const scrollRef = useRef<HTMLDivElement>(null)
  const loadTriggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = scrollRef.current
    const trigger = loadTriggerRef.current
    if (
      !root ||
      !trigger ||
      !hasMore ||
      loadingMore ||
      loadMoreError ||
      typeof IntersectionObserver === "undefined"
    ) {
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          onLoadMore()
        }
      },
      { root, rootMargin: "0px 0px 240px" },
    )
    observer.observe(trigger)
    return () => observer.disconnect()
  }, [hasMore, loadMoreError, loadingMore, onLoadMore])

  return (
    <div ref={scrollRef} className="min-h-0 flex-1 overflow-x-auto overflow-y-auto">
      <Table
        aria-label="Form submissions"
        className="table-fixed border-collapse text-left"
        style={tableStyle}
      >
        <colgroup>
          {colStyles.map((col) => (
            <col key={col.key} style={col.style} />
          ))}
        </colgroup>
        <SubmissionTableHeader sort={sort} widthsApi={widthsApi} onSort={onSort} />
        <SubmissionTableBody
          empty={empty}
          emptyMessage={emptyMessage}
          rows={visibleRows}
          onTranscript={onTranscript}
        />
      </Table>
      <InfiniteLoadStatus
        triggerRef={loadTriggerRef}
        hasMore={hasMore}
        loadMoreError={loadMoreError}
        loadingMore={loadingMore}
        onLoadMore={onLoadMore}
      />
    </div>
  )
}

const SubmissionTableHeader = ({
  sort,
  widthsApi,
  onSort,
}: Pick<SubmissionsTableGridProps, "sort" | "widthsApi" | "onSort">) => (
  <TableHeader className="bg-ice-2">
    <TableRow>
      {COLUMNS.map((label) => (
        <DataColumnHeader
          key={label}
          label={label}
          sort={sort}
          onSort={onSort}
          onResizeStart={widthsApi.handleResizeStart}
          onResizeMove={widthsApi.handleResizeMove}
          onResizeEnd={widthsApi.handleResizeEnd}
          onResizeKeyDown={widthsApi.handleResizeKeyDown}
          onResizeReset={widthsApi.handleResizeReset}
        />
      ))}
    </TableRow>
  </TableHeader>
)

const SubmissionTableBody = ({
  empty,
  emptyMessage,
  rows,
  onTranscript,
}: {
  empty: boolean
  emptyMessage: string
  rows: SubmissionRow[]
  onTranscript: (id: string) => void
}) => (
  <TableBody>
    {empty ? (
      <TableRow>
        <TableCell colSpan={COLUMNS.length} className="text-mute px-4 py-10 text-center text-sm">
          {emptyMessage}
        </TableCell>
      </TableRow>
    ) : (
      rows.map((row) => <SubmissionRowView key={row.id} row={row} onTranscript={onTranscript} />)
    )}
  </TableBody>
)

const InfiniteLoadStatus = ({
  triggerRef,
  hasMore,
  loadMoreError,
  loadingMore,
  onLoadMore,
}: {
  triggerRef: React.Ref<HTMLDivElement>
  hasMore: boolean
  loadMoreError: boolean
  loadingMore: boolean
  onLoadMore: () => void
}) => (
  <div
    ref={triggerRef}
    aria-live="polite"
    className="border-line bg-paper flex min-h-12 items-center justify-center border-t px-4 py-3"
  >
    {loadingMore ? (
      <span className="text-mute inline-flex items-center gap-2 text-xs">
        <Spinner /> Loading older submissions…
      </span>
    ) : loadMoreError ? (
      <Button type="button" variant="link" className="text-steel text-xs" onClick={onLoadMore}>
        Loading stopped. Try again
      </Button>
    ) : hasMore ? (
      <span className="text-mute text-xs">Scroll for older submissions</span>
    ) : (
      <span className="text-mute text-xs">All loaded submissions are shown</span>
    )}
  </div>
)
