"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Unblock and retry close over the current row. */

import { formatWhen } from "@/app/data/data-shared"
import { RetryError } from "@/components/admin/retry-error"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

import type { BlockedVisitor } from "./blocked-model"
import { useBlockedState } from "./use-blocked-state"

export const BlockedConsole = () => {
  const state = useBlockedState()

  return (
    <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
      <StaffHeader
        title="Blocked"
        description="Blocked identifiers cannot start or continue a chat on that site."
      />
      <div id="main-content" className="px-5 py-6 lg:px-8 lg:py-8">
        <BlockedBody state={state} />
      </div>
      <p className="sr-only" aria-live="polite">
        {state.announcement}
      </p>
    </div>
  )
}

const BlockedBody = ({ state }: { state: ReturnType<typeof useBlockedState> }) => {
  if (state.loadError) {
    return <RetryError text="Blocked visitors could not be loaded." onRetry={state.handleRetry} />
  }
  if (state.rows === null) {
    return <p className="text-mute text-sm">Loading blocked visitors…</p>
  }
  if (state.rows.length === 0) {
    return (
      <section className="border-line bg-paper rounded-[8px] border px-6 py-16 text-center">
        <p className="text-navy heading text-sm">No blocked visitors</p>
        <p className="text-mute mt-2 text-sm">
          Block a visitor from Data or the inbox. They will appear here until you unblock them.
        </p>
      </section>
    )
  }
  return <BlockedTable state={state} rows={state.rows} />
}

const BlockedTable = ({
  state,
  rows,
}: {
  state: ReturnType<typeof useBlockedState>
  rows: BlockedVisitor[]
}) => (
  <section
    aria-label="Blocked visitors"
    className="border-line bg-paper overflow-hidden rounded-lg border"
  >
    {state.rowError ? (
      <p className="text-ember px-5 py-3 text-sm" role="alert">
        {state.rowError}
      </p>
    ) : null}
    <table className="w-full text-left text-sm">
      <thead className="bg-ice-2 text-mute text-xs font-semibold tracking-[0.08em] uppercase">
        <tr>
          <th className="px-5 py-3">Site</th>
          <th className="px-5 py-3">Email</th>
          <th className="px-5 py-3">Phone</th>
          <th className="px-5 py-3">IP</th>
          <th className="px-5 py-3">Blocked by</th>
          <th className="px-5 py-3">Blocked on</th>
          <th className="px-5 py-3">
            <span className="sr-only">Unblock</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <BlockedRow
            key={row.id}
            row={row}
            pendingId={state.pendingId}
            onUnblock={state.handleUnblock}
          />
        ))}
      </tbody>
    </table>
  </section>
)

const BlockedRow = ({
  row,
  pendingId,
  onUnblock,
}: {
  row: BlockedVisitor
  pendingId: string | null
  onUnblock: (row: BlockedVisitor) => Promise<void>
}) => {
  const handleUnblock = () => {
    void onUnblock(row)
  }
  return (
    <tr className="border-line border-t">
      <td className="text-ink px-5 py-3">{row.site_name}</td>
      <td className="text-ink px-5 py-3 font-mono text-xs">{row.email ?? "—"}</td>
      <td className="text-ink px-5 py-3 font-mono text-xs">{row.phone ?? "—"}</td>
      <td className="text-ink px-5 py-3 font-mono text-xs">{row.ip ?? "—"}</td>
      <td className="text-ink px-5 py-3">{row.created_by_name}</td>
      <td className="text-mute px-5 py-3 text-xs">{formatWhen(row.created_at)}</td>
      <td className="px-5 py-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={pendingId === row.id}
          onClick={handleUnblock}
          aria-label={`Unblock visitor on ${row.site_name}`}
        >
          {pendingId === row.id ? <Spinner data-icon="inline-start" /> : null}
          Unblock
        </Button>
      </td>
    </tr>
  )
}
