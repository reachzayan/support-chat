"use client"

import { useEffect, useState } from "react"

import { staffRead, type SiteRecord } from "@/components/admin/staff-api"

export const useSitesList = () => {
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retryNonce, setRetryNonce] = useState(0)

  useEffect(() => {
    const request = retryNonce
    const load = async () => {
      try {
        const response = await staffRead("/api/sites")
        if (request !== retryNonce) {
          return
        }
        if (!response.ok) {
          setError("Sites could not be loaded")
          return
        }
        const body = (await response.json()) as { items: SiteRecord[] }
        setError(null)
        setSites(body.items)
        setLoaded(true)
      } catch {
        if (request !== retryNonce) {
          return
        }
        setError("Sites could not be loaded")
      }
    }
    void load()
  }, [retryNonce])

  const handleRetry = () => setRetryNonce((current) => current + 1)
  return { sites, loaded, setSites, error, setError, handleRetry }
}
