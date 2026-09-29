"use client"

import { useCallback, useEffect, useState } from "react"

import { staffRead, staffWrite } from "@/components/admin/staff-api"

import type { BlockedVisitor } from "./blocked-model"

export const useBlockedState = () => {
  const [rows, setRows] = useState<BlockedVisitor[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [rowError, setRowError] = useState("")
  const [announcement, setAnnouncement] = useState("")
  const [retryNonce, setRetryNonce] = useState(0)

  useEffect(() => {
    const request = retryNonce
    const load = async () => {
      try {
        const response = await staffRead("/api/visitor-blocks")
        if (request !== retryNonce) {
          return
        }
        if (!response.ok) {
          setLoadError(true)
          setRows(null)
          return
        }
        const body = (await response.json()) as { items: BlockedVisitor[] }
        setLoadError(false)
        setRows(body.items)
      } catch {
        if (request !== retryNonce) {
          return
        }
        setLoadError(true)
        setRows(null)
      }
    }
    void load()
  }, [retryNonce])

  const handleRetry = useCallback(() => setRetryNonce((current) => current + 1), [])

  const handleUnblock = useCallback(
    async (row: BlockedVisitor) => {
      if (pendingId) {
        return
      }
      setPendingId(row.id)
      setRowError("")
      try {
        const response = await staffWrite(`/api/visitor-blocks/${row.id}`, "DELETE", {})
        if (!response.ok) {
          setRowError("The visitor could not be unblocked. Try again.")
          return
        }
        setRows((current) => current?.filter((item) => item.id !== row.id) ?? null)
        setAnnouncement("Visitor unblocked.")
      } catch {
        setRowError("The visitor could not be unblocked. Try again.")
      } finally {
        setPendingId(null)
      }
    },
    [pendingId],
  )

  return {
    rows,
    loadError,
    pendingId,
    rowError,
    announcement,
    handleRetry,
    handleUnblock,
  }
}
