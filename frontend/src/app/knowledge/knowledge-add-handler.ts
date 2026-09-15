"use client"

import { useCallback, useState, type Dispatch, type SetStateAction } from "react"

import { staffWrite, type KbSourceRecord } from "@/components/admin/staff-api"
import { httpsUrlsError } from "@/lib/validation"

export const useKnowledgeAddHandler = (
  isAdmin: boolean,
  siteId: string,
  urls: string,
  setUrls: Dispatch<SetStateAction<string>>,
  setSources: Dispatch<SetStateAction<KbSourceRecord[]>>,
  setSourceId: Dispatch<SetStateAction<string | null>>,
) => {
  const [error, setError] = useState<string | null>(null)
  const clearError = useCallback(() => setError(null), [])
  const handleAdd = useCallback(async () => {
    if (!siteId || !isAdmin) {
      return false
    }
    const validationError = httpsUrlsError(urls)
    if (validationError) {
      setError(validationError)
      return false
    }
    const seed = urls
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
    if (seed.length === 0) {
      return false
    }
    const response = await staffWrite(`/api/sites/${siteId}/kb-sources`, "POST", {
      mode: "list",
      start_url: seed[0],
      seed_urls: seed,
    })
    if (!response.ok) {
      setError("Could not add this page. Check the URL and try again.")
      return false
    }
    const created = (await response.json()) as KbSourceRecord
    setSources((current) => [...current, created])
    setSourceId(created.id)
    setUrls("")
    setError(null)
    return true
  }, [isAdmin, setSourceId, setSources, setUrls, siteId, urls])
  return { handleAdd, error, clearError }
}
