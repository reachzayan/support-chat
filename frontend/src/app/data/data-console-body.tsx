"use client"

import { DataTableSkeleton } from "@/components/admin/loading-skeleton"

import type { SubmissionRow } from "./data-shared"
import { SubmissionsTable } from "./data-submissions-table"

export const DataConsoleBody = ({
  rows,
  loadError,
  hasMore,
  loadMoreError,
  loadingMore,
  onLoadMore,
  onTranscript,
}: {
  rows: SubmissionRow[] | null
  loadError: boolean
  hasMore: boolean
  loadMoreError: boolean
  loadingMore: boolean
  onLoadMore: () => void
  onTranscript: (id: string) => void
}) => {
  if (rows === null && !loadError) {
    return <DataTableSkeleton />
  }
  if (loadError) {
    return (
      <section className="border-line bg-paper rounded-[8px] border px-6 py-16 text-center">
        <p className="text-navy heading text-sm">Could not load submissions.</p>
        <p className="text-mute mt-2 text-sm">Try again in a moment.</p>
      </section>
    )
  }
  if (rows !== null && rows.length === 0) {
    return (
      <section className="border-line bg-paper rounded-[8px] border px-6 py-16 text-center">
        <p className="text-navy heading text-sm">No form submissions yet</p>
        <p className="text-mute mt-2 text-sm">
          Names, emails, and chat state appear here after a visitor fills the screening form.
        </p>
      </section>
    )
  }
  if (rows === null) {
    return null
  }
  return (
    <SubmissionsTable
      rows={rows}
      hasMore={hasMore}
      loadMoreError={loadMoreError}
      loadingMore={loadingMore}
      onLoadMore={onLoadMore}
      onTranscript={onTranscript}
    />
  )
}
