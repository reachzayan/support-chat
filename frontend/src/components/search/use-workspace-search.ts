"use client"
import { useEffect, useState } from "react"

import { staffRequest } from "@/lib/auth-client"

import {
  isSearchResults,
  navigationMatches,
  type SearchResults,
  type SearchScreen,
} from "./search-destinations"

type ResponseState = { key: string; results: SearchResults | null; failed: boolean }
export const useWorkspaceSearch = (
  query: string,
  screen: SearchScreen,
  isAdmin: boolean,
  enabled: boolean,
  retry: number,
) => {
  const trimmed = query.trim()
  const key = `${screen}:${trimmed}:${retry}`
  const [state, setState] = useState<ResponseState | null>(null)
  const searchable = trimmed.length >= 2
  useEffect(() => {
    if (!enabled || !searchable) return
    const controller = new AbortController()
    let active = true
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await staffRequest("/api/search", {
            method: "POST",
            signal: controller.signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: trimmed, screen }),
          })
          if (!response.ok) throw new Error("Search unavailable")
          const results: unknown = await response.json()
          if (!isSearchResults(results)) throw new Error("Invalid search response")
          if (active) setState({ key, results, failed: false })
        } catch {
          if (active) setState({ key, results: null, failed: true })
        }
      })()
    }, 180)
    return () => {
      active = false
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [enabled, searchable, trimmed, screen, key])
  const current = state?.key === key ? state : null
  const fallback = navigationMatches(trimmed, isAdmin)
  const results = current?.results ?? { current: [], navigation: fallback, other: [] }
  return {
    results,
    loading: enabled && searchable && current === null,
    failed: current?.failed ?? false,
    searchable,
  }
}
