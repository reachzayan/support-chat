"use client"

import { useState, type Dispatch, type SetStateAction } from "react"

import { staffWrite, type KbSourceRecord } from "@/components/admin/staff-api"
import { canonicalizeHttpsLines, httpsUrlsError } from "@/lib/validation"

const postSource = async (
  siteId: string,
  payload: Record<string, unknown>,
  fallbackError: string,
): Promise<{ created?: KbSourceRecord; error?: string }> => {
  const response = await staffWrite(`/api/sites/${siteId}/kb-sources`, "POST", payload)
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    return { error: body?.detail ?? fallbackError }
  }
  return { created: (await response.json()) as KbSourceRecord }
}

export const useKnowledgeAddHandler = (
  isAdmin: boolean,
  siteId: string,
  urls: string,
  setUrls: Dispatch<SetStateAction<string>>,
  setSources: Dispatch<SetStateAction<KbSourceRecord[]>>,
  setSourceId: Dispatch<SetStateAction<string | null>>,
) => {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const clearError = () => setError(null)
  const storeCreated = (created: KbSourceRecord) => {
    setSources((current) => {
      const next = current.filter(
        (row) =>
          row.id !== created.id &&
          (created.source_kind === "text" || row.start_url !== created.start_url),
      )
      return [...next, created]
    })
    setSourceId(created.id)
    setError(null)
  }
  const handleAdd = async () => {
    if (!siteId || !isAdmin) return false
    const validationError = httpsUrlsError(urls)
    if (validationError) {
      setError(validationError)
      return false
    }
    const seed = canonicalizeHttpsLines(urls)
    if (seed.length === 0) {
      return false
    }
    setBusy(true)
    try {
      const result = await postSource(
        siteId,
        { mode: seed.length > 1 ? "list" : "prefix", start_url: seed[0], seed_urls: seed },
        "Could not add this page. Check the URL and try again.",
      )
      if (!result.created) {
        setError(result.error ?? "Could not add this page.")
        return false
      }
      storeCreated(result.created)
      setUrls("")
      return true
    } finally {
      setBusy(false)
    }
  }
  const handleAddText = async (title: string, body: string) => {
    if (!siteId || !isAdmin) return false
    if (!title.trim() || !body.trim()) {
      setError("Add a title and content before continuing.")
      return false
    }
    setBusy(true)
    try {
      const result = await postSource(
        siteId,
        { kind: "text", title: title.trim(), body: body.trim() },
        "Could not add this text. Check the content and try again.",
      )
      if (!result.created) {
        setError(result.error ?? "Could not add this text.")
        return false
      }
      storeCreated(result.created)
      return true
    } finally {
      setBusy(false)
    }
  }
  return { handleAdd, handleAddText, busy, error, clearError }
}
