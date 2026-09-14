"use client"

import { useCallback, useEffect, useState } from "react"

import { StaffHeader } from "@/components/admin/staff-nav"
import { staffGet } from "@/lib/auth-client"

import { DataConsoleBody } from "./data-console-body"
import { SubmissionDetailSheet } from "./data-detail-sheet"
import type { SubmissionRow } from "./data-shared"

export const DataConsole = () => {
  const [rows, setRows] = useState<SubmissionRow[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    const load = async () => {
      const response = await staffGet("/api/conversations/submissions")
      if (!response.ok) {
        if (!ignore) {
          setLoadError(true)
          setRows(null)
        }
        return
      }
      const body = (await response.json()) as { items: SubmissionRow[] }
      if (!ignore) {
        setLoadError(false)
        setRows(body.items)
      }
    }
    void load()
    return () => {
      ignore = true
    }
  }, [])

  const handleOpenTranscript = useCallback((id: string) => {
    setSelectedId(id)
  }, [])

  const handleSheetOpen = useCallback((open: boolean) => {
    if (!open) {
      setSelectedId(null)
    }
  }, [])

  const selected = rows?.find((row) => row.id === selectedId) ?? null

  return (
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0">
        <StaffHeader title="Data" />
      </div>
      <div
        id="main-content"
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-5 py-5 lg:px-8 lg:py-8"
      >
        <DataConsoleBody rows={rows} loadError={loadError} onTranscript={handleOpenTranscript} />
      </div>
      {selectedId && selected ? (
        <SubmissionDetailSheet key={selectedId} row={selected} onClose={handleSheetOpen} />
      ) : null}
    </div>
  )
}
