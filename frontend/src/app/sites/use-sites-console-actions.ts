"use client"

import { useCallback, useState } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"

import type { ModalKind } from "./sites-shared"

export const useSitesConsoleActions = (
  setSites: React.Dispatch<React.SetStateAction<SiteRecord[]>>,
  setError: React.Dispatch<React.SetStateAction<string | null>>,
) => {
  const [modal, setModal] = useState<ModalKind>(null)
  const [activeId, setActiveId] = useState<string | null>(null)

  const handleSaved = useCallback(
    (next: SiteRecord) => {
      setSites((current) => current.map((row) => (row.id === next.id ? next : row)))
    },
    [setSites],
  )
  const handleCreated = useCallback(
    (next: SiteRecord) => {
      setSites((current) => [...current, next])
      setError(null)
      setModal(null)
      setActiveId(null)
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
    handleSaved,
    handleCreated,
    handleDeleted,
    handleCloseModal,
    handleOpenAdd,
    handleOpenManage,
    handleOpenDelete,
  }
}
