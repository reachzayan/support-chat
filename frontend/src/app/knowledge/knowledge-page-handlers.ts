"use client"

import { useCallback, type Dispatch, type SetStateAction } from "react"

import {
  staffRead,
  staffWrite,
  type KbPageDetail,
  type KbPageRecord,
} from "@/components/admin/staff-api"

export const useKnowledgePageHandlers = (
  setPages: Dispatch<SetStateAction<KbPageRecord[]>>,
  setPageDetail: Dispatch<SetStateAction<KbPageDetail | null>>,
) => {
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

  return { handleSelectPage, handleTogglePage }
}
