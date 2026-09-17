"use client"

import { useCallback, type ChangeEvent, type Dispatch, type SetStateAction } from "react"

import { staffWrite, type KbPageDetail, type KbSourceRecord } from "@/components/admin/staff-api"

import { useKnowledgeAddHandler } from "./knowledge-add-handler"

const syncSource = async (source: KbSourceRecord) =>
  staffWrite(`/api/kb-sources/${source.id}/sync`, "POST", {})

const toggleSource = async (source: KbSourceRecord) =>
  staffWrite(`/api/kb-sources/${source.id}`, "PATCH", { enabled: !source.enabled })

const deleteSource = async (source: KbSourceRecord) =>
  staffWrite(`/api/kb-sources/${source.id}`, "DELETE", {})

export const useKnowledgeSourceHandlers = (
  isAdmin: boolean,
  siteId: string,
  urls: string,
  setUrls: Dispatch<SetStateAction<string>>,
  setSources: Dispatch<SetStateAction<KbSourceRecord[]>>,
  setSourceId: Dispatch<SetStateAction<string | null>>,
  setPageDetail: Dispatch<SetStateAction<KbPageDetail | null>>,
) => {
  const {
    handleAdd,
    handleAddText,
    busy: addBusy,
    error: addError,
    clearError,
  } = useKnowledgeAddHandler(isAdmin, siteId, urls, setUrls, setSources, setSourceId)
  const handleUrls = useCallback(
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      setUrls(event.target.value)
      clearError()
    },
    [clearError, setUrls],
  )
  const handleSelectSource = useCallback(
    (source: KbSourceRecord) => {
      setSourceId(source.id)
      setPageDetail((current) =>
        current !== null && current.source_id === source.id ? current : null,
      )
    },
    [setPageDetail, setSourceId],
  )
  const handleSync = useCallback(
    async (source: KbSourceRecord) => {
      const response = await syncSource(source)
      if (response.ok) {
        const next = (await response.json()) as KbSourceRecord
        setSources((current) => current.map((row) => (row.id === next.id ? next : row)))
      }
    },
    [setSources],
  )
  const handleToggleSource = useCallback(
    async (source: KbSourceRecord) => {
      const response = await toggleSource(source)
      if (response.ok) {
        const next = (await response.json()) as KbSourceRecord
        setSources((current) => current.map((row) => (row.id === next.id ? next : row)))
      }
    },
    [setSources],
  )
  const handleDelete = useCallback(
    async (source: KbSourceRecord) => {
      const response = await deleteSource(source)
      if (!response.ok && response.status !== 204) {
        return
      }
      setSources((current) => current.filter((row) => row.id !== source.id))
      setSourceId((current) => (current === source.id ? null : current))
      setPageDetail((current) =>
        current !== null && current.source_id === source.id ? null : current,
      )
    },
    [setPageDetail, setSourceId, setSources],
  )

  return {
    handleUrls,
    handleAdd,
    handleAddText,
    addBusy,
    addError,
    handleSelectSource,
    handleSync,
    handleToggleSource,
    handleDelete,
  }
}
