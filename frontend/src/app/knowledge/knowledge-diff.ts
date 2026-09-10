"use client"

import { useCallback, useRef, useState, type SetStateAction } from "react"

import {
  staffRead,
  staffWrite,
  type KbDiff,
  type KbSnapshotRecord,
  type KbSourceRecord,
} from "@/components/admin/staff-api"

const rollbackSources = async (source: KbSourceRecord) => {
  const listed = await staffRead(`/api/sites/${source.site_id}/kb-sources`)
  if (!listed.ok) {
    return null
  }
  const payload = (await listed.json()) as { items: KbSourceRecord[] }
  return payload.items
}

const loadDiffPayload = async (source: KbSourceRecord) => {
  const [diffResponse, snapResponse] = await Promise.all([
    staffRead(`/api/kb-sources/${source.id}/diff`),
    staffRead(`/api/kb-sources/${source.id}/snapshots`),
  ])
  if (!diffResponse.ok) {
    return null
  }
  const payload = (await diffResponse.json()) as KbDiff
  let snapshots: KbSnapshotRecord[] = []
  if (snapResponse.ok) {
    const listed = (await snapResponse.json()) as { items: KbSnapshotRecord[] }
    snapshots = listed.items
  }
  return { payload, snapshots }
}

const formatDiffStatus = (payload: KbDiff, hasSuperseded: boolean) => {
  const added = payload.added.length
  const changed = payload.changed.length
  const removed = payload.removed.length
  return hasSuperseded
    ? `${added} added, ${changed} changed, ${removed} removed. A previous snapshot can be restored.`
    : `${added} added, ${changed} changed, ${removed} removed.`
}

export const useKnowledgeDiff = (setSources: (value: SetStateAction<KbSourceRecord[]>) => void) => {
  const [diffSource, setDiffSource] = useState<KbSourceRecord | null>(null)
  const [diff, setDiff] = useState<KbDiff | null>(null)
  const [diffStatus, setDiffStatus] = useState("Select a source to view snapshot changes.")
  const [canRollback, setCanRollback] = useState(false)
  const [rollbackBusy, setRollbackBusy] = useState(false)
  const diffRequestRef = useRef(0)

  const handleViewChanges = useCallback(async (source: KbSourceRecord) => {
    const requestId = diffRequestRef.current + 1
    diffRequestRef.current = requestId
    setDiffSource(source)
    setDiff(null)
    setDiffStatus("Loading snapshot changes.")
    setCanRollback(false)
    const loaded = await loadDiffPayload(source)
    if (diffRequestRef.current !== requestId || loaded === null) {
      if (loaded === null && diffRequestRef.current === requestId) {
        setDiffStatus("Could not load snapshot changes.")
      }
      return
    }
    const hasSuperseded = loaded.snapshots.some((row) => row.state === "superseded")
    setDiff(loaded.payload)
    setCanRollback(hasSuperseded)
    setDiffStatus(formatDiffStatus(loaded.payload, hasSuperseded))
  }, [])

  const handleDiffOpen = useCallback((open: boolean) => {
    if (!open) {
      setDiffSource(null)
      setDiff(null)
      setCanRollback(false)
      setDiffStatus("Select a source to view snapshot changes.")
    }
  }, [])

  const handleRollback = useCallback(async () => {
    if (diffSource === null || rollbackBusy) {
      return
    }
    const source = diffSource
    const requestId = diffRequestRef.current
    const stale = () => diffRequestRef.current !== requestId || diffSource.id !== source.id
    setRollbackBusy(true)
    setDiffStatus("Rolling back to the previous snapshot.")
    const response = await staffWrite(`/api/kb-sources/${source.id}/rollback`, "POST", {})
    if (stale()) {
      setRollbackBusy(false)
      return
    }
    if (!response.ok) {
      setDiffStatus("Rollback failed.")
      setRollbackBusy(false)
      return
    }
    const refreshed = await rollbackSources(source)
    if (refreshed !== null && !stale()) {
      setSources(refreshed)
    }
    if (!stale()) {
      await handleViewChanges(source)
      if (!stale()) {
        setDiffStatus("Rolled back to the previous snapshot.")
      }
    }
    setRollbackBusy(false)
  }, [diffSource, handleViewChanges, rollbackBusy, setSources])

  return {
    handleViewChanges,
    handleDiffOpen,
    handleRollback,
    diffSource,
    diff,
    diffStatus,
    canRollback,
    rollbackBusy,
  }
}
