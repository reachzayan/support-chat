"use client"

import { useCallback, useEffect, useState } from "react"

import { StaffHeader } from "@/components/admin/staff-nav"
import { staffGet } from "@/lib/auth-client"

import { DataConsoleBody } from "./data-console-body"
import { SubmissionDetailSheet } from "./data-detail-sheet"
import type { SubmissionRow } from "./data-shared"

const submissionsPath = (cursor: string | null) =>
  cursor === null
    ? "/api/conversations/submissions"
    : `/api/conversations/submissions?cursor=${encodeURIComponent(cursor)}`

const useSubmissionsFeed = () => {
  const [rows, setRows] = useState<SubmissionRow[] | null>(null)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)

  const loadPage = useCallback(async (cursor: string | null, append: boolean) => {
    const response = await staffGet(submissionsPath(cursor))
    if (!response.ok) {
      if (!append) {
        setLoadError(true)
        setRows(null)
        setNextCursor(null)
      }
      return false
    }
    const body = (await response.json()) as {
      items: SubmissionRow[]
      next_cursor?: string | null
    }
    setLoadError(false)
    setRows((current) => (append && current ? [...current, ...body.items] : body.items))
    setNextCursor(body.next_cursor ?? null)
    return true
  }, [])

  useEffect(() => {
    let ignore = false
    const boot = async () => {
      const ok = await loadPage(null, false)
      if (ignore || ok) {
        return
      }
      setLoadError(true)
    }
    void boot()
    return () => {
      ignore = true
    }
  }, [loadPage])

  const handleLoadMore = useCallback(async () => {
    if (!nextCursor || loadingMore) {
      return
    }
    setLoadingMore(true)
    await loadPage(nextCursor, true)
    setLoadingMore(false)
  }, [loadPage, loadingMore, nextCursor])

  return { rows, nextCursor, loadError, loadingMore, handleLoadMore }
}

export const DataConsole = () => {
  const { rows, nextCursor, loadError, loadingMore, handleLoadMore } = useSubmissionsFeed()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = rows?.find((row) => row.id === selectedId) ?? null

  const handleSheetOpen = useCallback((open: boolean) => {
    if (!open) {
      setSelectedId(null)
    }
  }, [])

  return (
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0">
        <StaffHeader title="Data" />
      </div>
      <div
        id="main-content"
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-5 py-5 lg:px-8 lg:py-8"
      >
        <DataConsoleBody
          rows={rows}
          loadError={loadError}
          hasMore={nextCursor !== null}
          loadingMore={loadingMore}
          onLoadMore={handleLoadMore}
          onTranscript={setSelectedId}
        />
      </div>
      {selectedId && selected ? (
        <SubmissionDetailSheet key={selectedId} row={selected} onClose={handleSheetOpen} />
      ) : null}
    </div>
  )
}
