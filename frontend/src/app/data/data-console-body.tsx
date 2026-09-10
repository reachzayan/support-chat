"use client"

import type { SubmissionRow } from "./data-shared"
import { SubmissionsTable } from "./data-submissions-table"

export const DataConsoleBody = ({
  rows,
  loadError,
  onTranscript,
}: {
  rows: SubmissionRow[] | null
  loadError: boolean
  onTranscript: (id: string) => void
}) => {
  if (rows === null && !loadError) {
    return <p className="text-mute text-sm">Loading submissions…</p>
  }
  if (loadError) {
    return (
      <section className="border-line bg-paper rounded-[8px] border px-6 py-16 text-center">
        <p className="text-navy text-sm font-extrabold">Could not load submissions.</p>
        <p className="text-mute mt-2 text-sm">
          The submissions export is capped at 200 rows. Try again in a moment.
        </p>
      </section>
    )
  }
  if (rows !== null && rows.length === 0) {
    return (
      <section className="border-line bg-paper rounded-[8px] border px-6 py-16 text-center">
        <p className="text-navy text-sm font-extrabold">No form submissions yet</p>
        <p className="text-mute mt-2 text-sm">
          Names, emails, and chat state appear here after a visitor fills the screening form.
        </p>
      </section>
    )
  }
  if (rows === null) {
    return null
  }
  return <SubmissionsTable rows={rows} onTranscript={onTranscript} />
}
