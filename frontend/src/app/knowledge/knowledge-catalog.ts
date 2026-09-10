"use client"

import { useCallback, useEffect, useState } from "react"

import {
  staffRead,
  type KbPageDetail,
  type KbPageRecord,
  type KbSourceRecord,
  type SiteRecord,
} from "@/components/admin/staff-api"

import { useKnowledgePageHandlers } from "./knowledge-page-handlers"
import { useKnowledgeSourceHandlers } from "./knowledge-source-handlers"

const KB_SOURCE_POLL_MS = 2_000

const sourceIngestPending = (sources: KbSourceRecord[]) =>
  sources.some((row) => {
    if (row.status === "queued" || row.status === "running") {
      return true
    }
    const stage = row.stage
    return (
      stage === "discovering" ||
      stage === "processing" ||
      stage === "validating" ||
      stage === "promoting"
    )
  })

const useKnowledgeSites = () => {
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [siteId, setSiteId] = useState("")

  useEffect(() => {
    const load = async () => {
      const response = await staffRead("/api/sites")
      if (!response.ok) {
        return
      }
      const payload = (await response.json()) as { items: SiteRecord[] }
      setSites(payload.items)
      if (payload.items[0]) {
        setSiteId(payload.items[0].id)
      }
    }
    void load()
  }, [])

  const handleSite = useCallback((nextSiteId: string) => {
    setSiteId(nextSiteId)
  }, [])

  return { sites, siteId, handleSite }
}

const useKnowledgeSources = (siteId: string) => {
  const [sources, setSources] = useState<KbSourceRecord[]>([])
  const [sourceId, setSourceId] = useState<string | null>(null)

  useEffect(() => {
    if (!siteId) {
      return
    }
    let ignore = false
    const load = async () => {
      const response = await staffRead(`/api/sites/${siteId}/kb-sources`)
      if (ignore || !response.ok) {
        return
      }
      const payload = (await response.json()) as { items: KbSourceRecord[] }
      setSources(payload.items)
      if (payload.items[0]) {
        setSourceId(payload.items[0].id)
      }
    }
    void load()
    return () => {
      ignore = true
    }
  }, [siteId])

  const ingestPending = sourceIngestPending(sources)
  useEffect(() => {
    if (!siteId || !ingestPending) {
      return
    }
    let ignore = false
    const load = async () => {
      const response = await staffRead(`/api/sites/${siteId}/kb-sources`)
      if (ignore || !response.ok) {
        return
      }
      const payload = (await response.json()) as { items: KbSourceRecord[] }
      setSources(payload.items)
    }
    const timer = window.setInterval(() => void load(), KB_SOURCE_POLL_MS)
    return () => {
      ignore = true
      window.clearInterval(timer)
    }
  }, [ingestPending, siteId])

  const resetForSite = useCallback(() => {
    setSources([])
    setSourceId(null)
  }, [])

  return { sources, sourceId, setSources, setSourceId, resetForSite }
}

const useKnowledgePages = (sources: KbSourceRecord[]) => {
  const [pages, setPages] = useState<KbPageRecord[]>([])
  const [pageDetail, setPageDetail] = useState<KbPageDetail | null>(null)
  const pageRefreshKey = sources.map((row) => `${row.id}:${row.page_count}:${row.status}`).join("|")

  useEffect(() => {
    if (pageRefreshKey === "") {
      return
    }
    let ignore = false
    const load = async () => {
      const lists = await Promise.all(
        sources.map(async (source) => {
          const response = await staffRead(`/api/kb-sources/${source.id}/pages`)
          if (!response.ok) {
            return [] as KbPageRecord[]
          }
          const payload = (await response.json()) as { items: KbPageRecord[] }
          return payload.items
        }),
      )
      if (ignore) {
        return
      }
      const flat = lists.flat()
      setPages(flat)
      if (flat[0] === undefined) {
        setPageDetail(null)
        return
      }
      const detailResponse = await staffRead(`/api/kb-pages/${flat[0].id}`)
      if (!ignore && detailResponse.ok) {
        setPageDetail((await detailResponse.json()) as KbPageDetail)
      }
    }
    void load()
    return () => {
      ignore = true
    }
  }, [pageRefreshKey, sources])

  const resetPages = useCallback(() => {
    setPages([])
    setPageDetail(null)
  }, [])

  return { pages, pageDetail, setPages, setPageDetail, resetPages }
}

export const useKnowledgeCatalog = (isAdmin: boolean) => {
  const [urls, setUrls] = useState("")
  const { sites, siteId, handleSite: selectSite } = useKnowledgeSites()
  const { sources, setSources, setSourceId, resetForSite } = useKnowledgeSources(siteId)
  const { pages, pageDetail, setPages, setPageDetail, resetPages } = useKnowledgePages(sources)

  const handleSite = useCallback(
    (nextSiteId: string) => {
      selectSite(nextSiteId)
      resetForSite()
      resetPages()
    },
    [resetForSite, resetPages, selectSite],
  )

  const sourceHandlers = useKnowledgeSourceHandlers(
    isAdmin,
    siteId,
    urls,
    setUrls,
    setSources,
    setSourceId,
    setPageDetail,
  )
  const pageHandlers = useKnowledgePageHandlers(setPages, setPageDetail)

  return {
    sites,
    siteId,
    sources,
    pages,
    pageDetail,
    urls,
    setSources,
    handleSite,
    ...sourceHandlers,
    ...pageHandlers,
  }
}
