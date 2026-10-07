"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- StaffHeader export action uses the current page state. */

import { useCallback, useEffect, useRef, useState } from "react"

import { StaffHeader } from "@/components/admin/staff-nav"
import { useSearchTarget } from "@/components/search/workspace-route"
import { Button } from "@/components/ui/button"
import { staffGet } from "@/lib/auth-client"

import { DataConsoleBody } from "./data-console-body"
import { SubmissionDetailSheet } from "./data-detail-sheet"
import { DataExportDialog } from "./data-export-dialog"
import type { SubmissionRow } from "./data-shared"

const PAGE_SIZE = 50

const submissionsPath = (offset: number) =>
  `/api/conversations/submissions?offset=${offset}&limit=${PAGE_SIZE}`

const useSubmissionsFeed = () => {
  const [rows, setRows] = useState<SubmissionRow[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState(false)
  const loadingMoreRef = useRef(false)
  const nextOffsetRef = useRef(0)

  const loadPage = useCallback(async (offset: number, append: boolean) => {
    try {
      const response = await staffGet(submissionsPath(offset))
      if (!response.ok) {
        if (append) {
          setLoadMoreError(true)
        } else {
          setLoadError(true)
          setRows(null)
          setHasMore(false)
        }
        return false
      }
      const body = (await response.json()) as {
        items: SubmissionRow[]
        has_more?: boolean
      }
      nextOffsetRef.current = offset + body.items.length
      setLoadError(false)
      setLoadMoreError(false)
      setRows((current) => {
        if (!append || current === null) {
          return body.items
        }
        const byId = new Map(current.map((row) => [row.id, row]))
        for (const row of body.items) {
          byId.set(row.id, row)
        }
        return Array.from(byId.values())
      })
      setHasMore(Boolean(body.has_more) && body.items.length > 0)
      return true
    } catch {
      if (append) {
        setLoadMoreError(true)
      } else {
        setLoadError(true)
        setRows(null)
        setHasMore(false)
      }
      return false
    }
  }, [])

  useEffect(() => {
    let ignore = false
    const boot = async () => {
      const ok = await loadPage(0, false)
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

  const handleLoadMore = async () => {
    if (!hasMore || loadingMoreRef.current) {
      return
    }
    loadingMoreRef.current = true
    setLoadingMore(true)
    try {
      await loadPage(nextOffsetRef.current, true)
    } finally {
      loadingMoreRef.current = false
      setLoadingMore(false)
    }
  }

  return { rows, hasMore, loadError, loadMoreError, loadingMore, handleLoadMore }
}

export const DataConsole = () => {
  const { rows, hasMore, loadError, loadMoreError, loadingMore, handleLoadMore } =
    useSubmissionsFeed()
  const target = useSearchTarget()
  const [selectedId, setSelectedId] = useState<string | null>(target.conversation ?? null)
  const [linkedRow, setLinkedRow] = useState<SubmissionRow | null>(null)
  const [selectionError, setSelectionError] = useState(false)
  useEffect(() => {
    if (!target.conversation) return
    let active = true
    void (async () => {
      try {
        const response = await staffGet(
          `/api/conversations/submissions/${encodeURIComponent(target.conversation)}`,
        )
        if (!response.ok) throw new Error("Unavailable submission")
        const row = (await response.json()) as SubmissionRow
        if (active) setLinkedRow(row)
      } catch {
        if (active) setSelectionError(true)
      }
    })()
    return () => {
      active = false
    }
  }, [target.conversation])
  const [exportOpen, setExportOpen] = useState(false)
  const selected =
    rows?.find((row) => row.id === selectedId) ?? (linkedRow?.id === selectedId ? linkedRow : null)

  const handleSheetOpen = useCallback((open: boolean) => {
    if (!open) {
      setSelectedId(null)
    }
  }, [])

  const handleOpenExport = useCallback(() => setExportOpen(true), [])
  const handleCloseExport = useCallback(() => setExportOpen(false), [])

  return (
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0">
        <StaffHeader
          title="Data"
          action={
            <Button variant="default" size="lg" className="font-bold" onClick={handleOpenExport}>
              Export
            </Button>
          }
        />
      </div>
      <div
        id="main-content"
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-5 py-5 lg:px-8 lg:py-8"
      >
        {selectionError ? (
          <p role="alert" className="text-ember mb-3 text-sm">
            This submission is no longer available. Search again for the latest records.
          </p>
        ) : null}
        <DataConsoleBody
          rows={rows}
          loadError={loadError}
          hasMore={hasMore}
          loadMoreError={loadMoreError}
          loadingMore={loadingMore}
          onLoadMore={handleLoadMore}
          onTranscript={setSelectedId}
        />
      </div>
      {selectedId && selected ? (
        <SubmissionDetailSheet key={selectedId} row={selected} onClose={handleSheetOpen} />
      ) : null}
      {exportOpen ? <DataExportDialog open={exportOpen} onClose={handleCloseExport} /> : null}
    </div>
  )
}
