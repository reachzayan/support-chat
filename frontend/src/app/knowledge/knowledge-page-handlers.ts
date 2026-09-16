"use client"

import { useCallback, useState, type Dispatch, type SetStateAction } from "react"

import {
  staffRead,
  staffWrite,
  type KbPageDetail,
  type KbChunkRecord,
  type KbPageRecord,
} from "@/components/admin/staff-api"

// oxlint-disable-next-line eslint/max-lines-per-function -- Page and chunk toggles share one local state boundary so rollback remains consistent.
export const useKnowledgePageHandlers = (
  setPages: Dispatch<SetStateAction<KbPageRecord[]>>,
  setPageDetail: Dispatch<SetStateAction<KbPageDetail | null>>,
) => {
  const [chunkErrors, setChunkErrors] = useState<Record<string, string>>({})
  const [chunkPendingIds, setChunkPendingIds] = useState<string[]>([])
  const [chunkNotice, setChunkNotice] = useState("")
  const handleSelectPage = useCallback(
    async (page: KbPageRecord) => {
      const response = await staffRead(`/api/kb-pages/${page.id}`)
      if (!response.ok) {
        return
      }
      setPageDetail((await response.json()) as KbPageDetail)
    },
    [setPageDetail],
  )

  const handleTogglePage = useCallback(
    async (page: KbPageRecord) => {
      const response = await staffWrite(`/api/kb-pages/${page.id}`, "PATCH", {
        enabled: !page.enabled,
      })
      if (response.ok) {
        const next = (await response.json()) as KbPageRecord
        setPages((current) => current.map((row) => (row.id === next.id ? next : row)))
        setPageDetail((current) =>
          current !== null && current.id === next.id
            ? { ...current, enabled: next.enabled }
            : current,
        )
      }
    },
    [setPageDetail, setPages],
  )

  const handleToggleChunk = useCallback(
    async (pageId: string, chunk: KbChunkRecord) => {
      if (chunkPendingIds.includes(chunk.id)) {
        return
      }
      const previous = chunk
      const enabled = !previous.enabled
      setChunkPendingIds((current) => [...current, chunk.id])
      setChunkErrors((current) => ({ ...current, [chunk.id]: "" }))
      setChunkNotice("")
      setPageDetail((current) =>
        current === null
          ? current
          : {
              ...current,
              chunks: current.chunks.map((item) =>
                item.id === chunk.id ? { ...item, enabled } : item,
              ),
            },
      )
      try {
        const response = await staffWrite(`/api/kb-chunks/${chunk.id}`, "PATCH", { enabled })
        if (response.status === 409) {
          const currentPage = await staffRead(`/api/kb-pages/${pageId}`)
          if (currentPage.ok) {
            setPageDetail((await currentPage.json()) as KbPageDetail)
          }
          setChunkNotice("This page changed during sync. Review the latest retrieved answers.")
          return
        }
        if (!response.ok) {
          throw new Error("This retrieved answer could not be updated. Try again.")
        }
        const saved = (await response.json()) as KbChunkRecord
        setPageDetail((current) =>
          current === null
            ? current
            : {
                ...current,
                chunks: current.chunks.map((item) => (item.id === saved.id ? saved : item)),
              },
        )
      } catch (error) {
        setPageDetail((current) =>
          current === null
            ? current
            : {
                ...current,
                chunks: current.chunks.map((item) => (item.id === previous.id ? previous : item)),
              },
        )
        setChunkErrors((current) => ({
          ...current,
          [chunk.id]:
            error instanceof Error ? error.message : "This retrieved answer could not be updated.",
        }))
      } finally {
        setChunkPendingIds((current) => current.filter((id) => id !== chunk.id))
      }
    },
    [chunkPendingIds, setPageDetail],
  )

  return {
    handleSelectPage,
    handleTogglePage,
    handleToggleChunk,
    chunkErrors,
    chunkPendingIds,
    chunkNotice,
  }
}
