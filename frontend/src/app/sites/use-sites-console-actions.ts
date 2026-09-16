"use client"

import { useCallback, useState } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"

import type { ModalKind } from "./sites-shared"

// oxlint-disable-next-line max-lines-per-function
export const useSitesConsoleActions = (
  setSites: React.Dispatch<React.SetStateAction<SiteRecord[]>>,
  setError: React.Dispatch<React.SetStateAction<string | null>>,
) => {
  const [modal, setModal] = useState<ModalKind>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [checkingIds, setCheckingIds] = useState<string[]>([])

  const handleSaved = useCallback(
    (next: SiteRecord) => {
      setSites((current) => current.map((row) => (row.id === next.id ? next : row)))
    },
    [setSites],
  )
  const handleCheckInstall = useCallback(
    async (siteId: string) => {
      setCheckingIds((current) => (current.includes(siteId) ? current : [...current, siteId]))
      try {
        const response = await staffWrite(`/api/sites/${siteId}/check-install`, "POST", {})
        if (!response.ok) {
          setError("Could not recheck the widget install status.")
          return
        }
        setError(null)
        handleSaved((await response.json()) as SiteRecord)
      } catch {
        setError("Could not recheck the widget install status.")
      } finally {
        setCheckingIds((current) => current.filter((id) => id !== siteId))
      }
    },
    [handleSaved, setError],
  )
  const handleCreated = useCallback(
    (next: SiteRecord) => {
      setSites((current) =>
        current.some((row) => row.id === next.id)
          ? current.map((row) => (row.id === next.id ? next : row))
          : [...current, next],
      )
      setError(null)
    },
    [setError, setSites],
  )
  const handleDeleted = useCallback(
    (siteId: string) => {
      setSites((current) => current.filter((row) => row.id !== siteId))
      setError(null)
      setModal(null)
      setActiveId(null)
    },
    [setError, setSites],
  )
  const handleCloseModal = useCallback(() => {
    setModal(null)
    setActiveId(null)
  }, [])
  const handleOpenAdd = useCallback(() => {
    setActiveId(null)
    setModal("add")
  }, [])
  const handleOpenManage = useCallback((siteId: string) => {
    setActiveId(siteId)
    setModal("manage")
  }, [])
  const handleOpenDelete = useCallback((siteId: string) => {
    setActiveId(siteId)
    setModal("delete")
  }, [])

  return {
    modal,
    activeId,
    checkingIds,
    handleSaved,
    handleCreated,
    handleDeleted,
    handleCloseModal,
    handleOpenAdd,
    handleOpenManage,
    handleOpenDelete,
    handleCheckInstall,
  }
}
