"use client"

import { useEffect, useState } from "react"

import { staffRead, type SiteRecord } from "@/components/admin/staff-api"

export const useSitesList = () => {
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      const response = await staffRead("/api/sites")
      if (!response.ok) {
        return
      }
      const body = (await response.json()) as { items: SiteRecord[] }
      setSites(body.items)
    }
    void load()
  }, [])

  return { sites, setSites, error, setError }
}
