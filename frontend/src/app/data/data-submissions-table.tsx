"use client"

import { useCallback, useMemo, useState, type CSSProperties } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import { useDataColumnWidths } from "./data-column-widths"
import {
  blank,
  COLUMNS,
  formatWhen,
  STATE_LABEL,
  stateClass,
  type ColumnLabel,
  type SubmissionRow,
} from "./data-shared"

const PAGE_SIZE = 10

const DataColumnHeader = ({
  label,
  onResizeStart,
  onResizeMove,
  onResizeEnd,
  onResizeKeyDown,
  onResizeReset,
}: {
  label: ColumnLabel
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

  return (
    <TableHead
      scope="col"
      className="text-ink bg-ice-2 sticky top-0 z-10 px-4 py-3 text-[10px] font-semibold tracking-[0.12em] uppercase"
    >
      <span className="pr-2">{label}</span>
      <button
        type="button"
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
      </button>
    </TableHead>
  )
}

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
        <button
          type="button"
          onClick={handleClick}
          aria-label={`Transcript for ${blank(row.visitor.name)}`}
          className="border-line text-navy hover:bg-ice focus-visible:ring-steel cursor-pointer rounded-[8px] border px-3 py-1.5 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
        >
          Transcript
        </button>
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
  loadingMore,
  onLoadMore,
  onTranscript,
}: {
  rows: SubmissionRow[]
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
  onTranscript: (id: string) => void
}) => {
  const [page, setPage] = useState(1)
  const widthsApi = useDataColumnWidths()
  const tableStyle = useMemo(
    () => ({ width: "100%", minWidth: widthsApi.tableWidth }),
    [widthsApi.tableWidth],
  )
  const colStyles = useMemo(
    () => COLUMNS.map((label) => ({ key: label, style: { width: widthsApi.widths[label] } })),
    [widthsApi.widths],
  )
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const visibleRows = rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  return (
    <section
      aria-label="Form submissions"
      className="border-line bg-paper flex min-h-0 flex-1 flex-col overflow-hidden rounded-[8px] border"
    >
      <div className="border-line flex shrink-0 items-baseline justify-between border-b px-5 py-4">
        <h2 className="text-navy heading text-sm">Submissions</h2>
        <p className="text-mute text-xs">{rows.length} loaded submissions</p>
      </div>
      <SubmissionsTableGrid
        tableStyle={tableStyle}
        colStyles={colStyles}
        widthsApi={widthsApi}
        visibleRows={visibleRows}
        onTranscript={onTranscript}
      />
      <div className="border-line flex shrink-0 items-center justify-between border-t px-5 py-3">
        <TablePagination currentPage={currentPage} pageCount={pageCount} onPage={setPage} />
        {hasMore ? (
          <button
            type="button"
            className="text-steel text-xs font-semibold disabled:opacity-50"
            disabled={loadingMore}
            onClick={onLoadMore}
          >
            {loadingMore ? "Loading…" : "Load older submissions"}
          </button>
        ) : null}
      </div>
    </section>
  )
}

const SubmissionsTableGrid = ({
  tableStyle,
  colStyles,
  widthsApi,
  visibleRows,
  onTranscript,
}: {
  tableStyle: CSSProperties
  colStyles: { key: string; style: CSSProperties }[]
  widthsApi: ReturnType<typeof useDataColumnWidths>
  visibleRows: SubmissionRow[]
  onTranscript: (id: string) => void
}) => (
  <div className="min-h-0 flex-1 overflow-x-auto overflow-y-auto">
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
      <TableHeader className="bg-ice-2">
        <TableRow>
          {COLUMNS.map((label) => (
            <DataColumnHeader
              key={label}
              label={label}
              onResizeStart={widthsApi.handleResizeStart}
              onResizeMove={widthsApi.handleResizeMove}
              onResizeEnd={widthsApi.handleResizeEnd}
              onResizeKeyDown={widthsApi.handleResizeKeyDown}
              onResizeReset={widthsApi.handleResizeReset}
            />
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {visibleRows.map((row) => (
          <SubmissionRowView key={row.id} row={row} onTranscript={onTranscript} />
        ))}
      </TableBody>
    </Table>
  </div>
)

const TablePagination = ({
  currentPage,
  pageCount,
  onPage,
}: {
  currentPage: number
  pageCount: number
  onPage: (page: number) => void
}) => {
  const handlePrevious = useCallback(
    (event: React.MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault()
      if (currentPage > 1) onPage(currentPage - 1)
    },
    [currentPage, onPage],
  )
  const handleNext = useCallback(
    (event: React.MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault()
      if (currentPage < pageCount) onPage(currentPage + 1)
    },
    [currentPage, onPage, pageCount],
  )
  const handlePage = useCallback(
    (event: React.MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault()
      const nextPage = Number(event.currentTarget.dataset.page)
      if (Number.isInteger(nextPage)) onPage(nextPage)
    },
    [onPage],
  )

  return (
    <Pagination className="border-line shrink-0 justify-end border-t px-5 py-3">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            href="#"
            aria-disabled={currentPage === 1}
            tabIndex={currentPage === 1 ? -1 : undefined}
            className={currentPage === 1 ? "pointer-events-none opacity-50" : undefined}
            onClick={handlePrevious}
          />
        </PaginationItem>
        {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => (
          <PaginationItem key={pageNumber}>
            <PaginationLink
              href="#"
              data-page={pageNumber}
              isActive={currentPage === pageNumber}
              aria-label={`Go to page ${pageNumber}`}
              onClick={handlePage}
            >
              {pageNumber}
            </PaginationLink>
          </PaginationItem>
        ))}
        <PaginationItem>
          <PaginationNext
            href="#"
            aria-disabled={currentPage === pageCount}
            tabIndex={currentPage === pageCount ? -1 : undefined}
            className={currentPage === pageCount ? "pointer-events-none opacity-50" : undefined}
            onClick={handleNext}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  )
}
