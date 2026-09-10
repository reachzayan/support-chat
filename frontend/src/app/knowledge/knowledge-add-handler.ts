"use client"

import { useCallback, type Dispatch, type SetStateAction } from "react"

import { staffWrite, type KbSourceRecord } from "@/components/admin/staff-api"

export const useKnowledgeAddHandler = (
  isAdmin: boolean,
  siteId: string,
  urls: string,
  setUrls: Dispatch<SetStateAction<string>>,
  setSources: Dispatch<SetStateAction<KbSourceRecord[]>>,
  setSourceId: Dispatch<SetStateAction<string | null>>,
) => {
  return useCallback(async () => {
    if (!siteId || !isAdmin) {
      return
    }
    const seed = urls
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
    if (seed.length === 0) {
      return
    }
    const response = await staffWrite(`/api/sites/${siteId}/kb-sources`, "POST", {
      mode: "list",
      start_url: seed[0],
      seed_urls: seed,
    })
    if (!response.ok) {
      return
    }
    const created = (await response.json()) as KbSourceRecord
    setSources((current) => [...current, created])
    setSourceId(created.id)
    setUrls("")
  }, [isAdmin, setSourceId, setSources, setUrls, siteId, urls])
}
