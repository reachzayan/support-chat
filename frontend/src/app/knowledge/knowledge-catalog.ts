"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import {
  staffRead,
  type KbPageDetail,
  type KbPageRecord,
  type KbProgressRecord,
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

const useKnowledgePages = (sources: KbSourceRecord[], sourceId: string | null) => {
  const [pages, setPages] = useState<KbPageRecord[]>([])
  const [pageDetail, setPageDetail] = useState<KbPageDetail | null>(null)
  const selectedPageIdRef = useRef<string | null>(null)
  const sourcesRef = useRef(sources)
  const sourceIdRef = useRef(sourceId)
  const pageRefreshKey = `${sourceId ?? ""}|${sources
    .map((row) => `${row.id}:${row.page_count}:${row.status}`)
    .join("|")}`

  useEffect(() => {
    selectedPageIdRef.current = pageDetail?.id ?? null
  }, [pageDetail])

  useEffect(() => {
    sourcesRef.current = sources
    sourceIdRef.current = sourceId
  }, [sourceId, sources])

  useEffect(() => {
    const selectedSourceId = sourceIdRef.current
    const allSources = sourcesRef.current
    const scopedSources = selectedSourceId
      ? allSources.filter((row) => row.id === selectedSourceId)
      : allSources
    let ignore = false
    const load = async () => {
      if (pageRefreshKey === "|" || scopedSources.length === 0) {
        if (!ignore) {
          setPages([])
          setPageDetail(null)
        }
        return
      }
      const lists = await Promise.all(
        scopedSources.map(async (source) => {
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
      const visible = lists.flat()
      setPages(visible)
      const selectedId = selectedPageIdRef.current
      const kept = selectedId ? visible.find((page) => page.id === selectedId) : undefined
      const next = kept ?? visible[0]
      if (next === undefined) {
        setPageDetail(null)
        return
      }
      const detailResponse = await staffRead(`/api/kb-pages/${next.id}`)
      if (!ignore && detailResponse.ok) {
        setPageDetail((await detailResponse.json()) as KbPageDetail)
      }
    }
    void load()
    return () => {
      ignore = true
    }
  }, [pageRefreshKey])

  const resetPages = useCallback(() => {
    setPages([])
    setPageDetail(null)
  }, [])

  return { pages, pageDetail, setPages, setPageDetail, resetPages }
}

const useKnowledgeProgress = (sourceId: string | null, sources: KbSourceRecord[]) => {
  const [progress, setProgress] = useState<KbProgressRecord | null>(null)
  const source = sources.find((row) => row.id === sourceId)
  const selectedSourceId = source?.id
  const status = source?.status

  useEffect(() => {
    if (!selectedSourceId) {
      return
    }
    let ignore = false
    const load = async () => {
      const response = await staffRead(`/api/kb-sources/${selectedSourceId}/progress`)
      if (!ignore && response.ok) {
        setProgress((await response.json()) as KbProgressRecord)
      }
    }
    void load()
    const timer =
      status === "queued" || status === "running"
        ? window.setInterval(() => void load(), KB_SOURCE_POLL_MS)
        : null
    return () => {
      ignore = true
      if (timer !== null) {
        window.clearInterval(timer)
      }
    }
  }, [selectedSourceId, status])

  return selectedSourceId ? progress : null
}

export const useKnowledgeCatalog = (isAdmin: boolean) => {
  const [urls, setUrls] = useState("")
  const { sites, siteId, handleSite: selectSite } = useKnowledgeSites()
  const { sources, sourceId, setSources, setSourceId, resetForSite } = useKnowledgeSources(siteId)
  const { pages, pageDetail, setPages, setPageDetail, resetPages } = useKnowledgePages(
    sources,
    sourceId,
  )
  const progress = useKnowledgeProgress(sourceId, sources)

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
  const pageHandlers = useKnowledgePageHandlers(setPages, setPageDetail, setSources)

  return {
    sites,
    siteId,
    sources,
    sourceId,
    pages,
    pageDetail,
    progress,
    urls,
    setSources,
    handleSite,
    ...sourceHandlers,
    ...pageHandlers,
  }
}
