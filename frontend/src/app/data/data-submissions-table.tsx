"use client"

import { useCallback, useMemo } from "react"

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
    <th
      scope="col"
      className="text-ink bg-ice-2 sticky top-0 z-10 px-4 py-3 text-[10px] font-bold tracking-[0.12em] uppercase"
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
    </th>
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
    <tr className="border-line odd:bg-paper even:bg-ice-2/60 border-t">
      <Cell>{blank(row.visitor.name)}</Cell>
      <Cell>{blank(row.visitor.email)}</Cell>
      <Cell>{blank(row.visitor.phone)}</Cell>
      <Cell>{blank(row.inquiry_type)}</Cell>
      <Cell>{blank(row.intent)}</Cell>
      <td className="px-4 py-3">
        <span
          className={`inline-flex rounded-[8px] px-2 py-0.5 text-[11px] font-bold ${stateClass(row.state)}`}
        >
          {STATE_LABEL[row.state] ?? row.state}
        </span>
      </td>
      <Cell>{row.site_name}</Cell>
      <Cell mono>{row.site_key}</Cell>
      <Cell>{blank(row.opening_message)}</Cell>
      <Cell>{blank(row.page.title)}</Cell>
      <Cell>{blank(row.page.url)}</Cell>
      <Cell>{blank(row.page.referrer)}</Cell>
      <Cell mono>{blank(row.visitor.ip)}</Cell>
      <Cell>{blank(row.visitor.user_agent)}</Cell>
      <Cell>{blank(row.visitor.geo_country)}</Cell>
      <Cell>{blank(row.visitor.geo_region)}</Cell>
      <Cell>{row.attention_needed ? "Yes" : "—"}</Cell>
      <Cell>{blank(row.assigned_agent?.display_name)}</Cell>
      <Cell>{formatWhen(row.visitor.created_at)}</Cell>
      <Cell>{formatWhen(row.created_at)}</Cell>
      <Cell>{formatWhen(row.last_message_at)}</Cell>
      <Cell>{formatWhen(row.closed_at)}</Cell>
      <td className="px-4 py-3">
        <button
          type="button"
          onClick={handleClick}
          aria-label={`Transcript for ${blank(row.visitor.name)}`}
          className="border-line text-navy hover:bg-ice focus-visible:ring-steel cursor-pointer rounded-[8px] border px-3 py-1.5 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
        >
          Transcript
        </button>
      </td>
    </tr>
  )
}

const Cell = ({ children, mono = false }: { children: string; mono?: boolean }) => (
  <td
    title={children === "—" ? undefined : children}
    className={`text-ink overflow-hidden px-4 py-3 text-xs wrap-break-word ${mono ? "font-mono" : ""}`}
  >
    {children}
  </td>
)

export const SubmissionsTable = ({
  rows,
  onTranscript,
}: {
  rows: SubmissionRow[]
  onTranscript: (id: string) => void
}) => {
  const {
    widths,
    tableWidth,
    handleResizeStart,
    handleResizeMove,
    handleResizeEnd,
    handleResizeKeyDown,
    handleResizeReset,
  } = useDataColumnWidths()
  const tableStyle = useMemo(() => ({ width: tableWidth }), [tableWidth])
  const colStyles = useMemo(
    () => COLUMNS.map((label) => ({ key: label, style: { width: widths[label] } })),
    [widths],
  )

  return (
    <section
      aria-label="Form submissions"
      className="border-line bg-paper flex min-h-0 flex-1 flex-col overflow-hidden rounded-[8px] border"
    >
      <div className="border-line flex shrink-0 items-baseline justify-between border-b px-5 py-4">
        <h2 className="text-navy text-sm font-extrabold">Submissions</h2>
        <p className="text-mute text-xs">{rows.length} people</p>
      </div>
      <div className="min-h-0 flex-1 overflow-x-auto overflow-y-auto">
        <table className="table-fixed border-collapse text-left" style={tableStyle}>
          <colgroup>
            {colStyles.map((col) => (
              <col key={col.key} style={col.style} />
            ))}
          </colgroup>
          <thead className="bg-ice-2">
            <tr>
              {COLUMNS.map((label) => (
                <DataColumnHeader
                  key={label}
                  label={label}
                  onResizeStart={handleResizeStart}
                  onResizeMove={handleResizeMove}
                  onResizeEnd={handleResizeEnd}
                  onResizeKeyDown={handleResizeKeyDown}
                  onResizeReset={handleResizeReset}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <SubmissionRowView key={row.id} row={row} onTranscript={onTranscript} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
