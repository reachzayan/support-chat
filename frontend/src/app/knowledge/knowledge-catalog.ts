"use client"

import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react"

import {
  staffRead,
  type KbPageDetail,
  type KbPageRecord,
  type KbSourceRecord,
  type SiteRecord,
} from "@/components/admin/staff-api"

import { useKnowledgePageHandlers } from "./knowledge-page-handlers"
import { resolveKnowledgeSiteId } from "./knowledge-site"
import { useKnowledgeSourceHandlers } from "./knowledge-source-handlers"

const sourceFingerprint = (row: KbSourceRecord) =>
  [
    row.id,
    row.page_count,
    row.status,
    row.stage ?? "",
    row.pages_embedded ?? "",
    row.last_run_finished_at ?? "",
    row.snapshot_state ?? "",
  ].join(":")

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

const applySourceList = (
  items: KbSourceRecord[],
  setSources: (items: KbSourceRecord[]) => void,
  setSourceId: Dispatch<SetStateAction<string | null>>,
) => {
  setSources(items)
  setSourceId((current) => {
    if (current !== null && items.some((row) => row.id === current)) {
      return current
    }
    return items[0]?.id ?? null
  })
}

const useKnowledgeSources = (siteId: string) => {
  const [sources, setSources] = useState<KbSourceRecord[]>([])
  const [sourceId, setSourceId] = useState<string | null>(null)
  const siteIdRef = useRef(siteId)

  const loadSources = useCallback(async () => {
    const currentSiteId = siteIdRef.current
    if (!currentSiteId) {
      return
    }
    const response = await staffRead(`/api/sites/${currentSiteId}/kb-sources`)
    if (!response.ok || siteIdRef.current !== currentSiteId) {
      return
    }
    const payload = (await response.json()) as { items: KbSourceRecord[] }
    if (siteIdRef.current !== currentSiteId) {
      return
    }
    applySourceList(payload.items, setSources, setSourceId)
  }, [])

  useEffect(() => {
    siteIdRef.current = siteId
    if (!siteId) {
      return
    }
    void loadSources()
  }, [loadSources, siteId])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible") {
        return
      }
      void loadSources()
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
  }, [loadSources])

  const resetForSite = useCallback(() => {
    setSources([])
    setSourceId(null)
  }, [])

  return { sources, sourceId, setSources, setSourceId, resetForSite }
}

const useKnowledgePages = (sources: KbSourceRecord[]) => {
  const [pages, setPages] = useState<KbPageRecord[]>([])
  const [pageDetail, setPageDetail] = useState<KbPageDetail | null>(null)
  const selectedPageIdRef = useRef<string | null>(null)
  const sourcesRef = useRef(sources)
  const pageRefreshKey = sources.map(sourceFingerprint).join("|")

  useEffect(() => {
    selectedPageIdRef.current = pageDetail?.id ?? null
  }, [pageDetail])

  useEffect(() => {
    sourcesRef.current = sources
  }, [sources])

  useEffect(() => {
    const allSources = sourcesRef.current
    let ignore = false
    const load = async () => {
      if (pageRefreshKey === "" || allSources.length === 0) {
        if (!ignore) {
          setPages([])
          setPageDetail(null)
        }
        return
      }
      const lists = await Promise.all(
        allSources.map(async (source) => {
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

export const useKnowledgeCatalog = (isAdmin: boolean) => {
  const [urls, setUrls] = useState("")
  const { sites, siteId, handleSite: selectSite } = useKnowledgeSites()
  const { sources, sourceId, setSources, setSourceId } = useKnowledgeSources(siteId)
  const { pages, pageDetail, setPages, setPageDetail } = useKnowledgePages(sources)
  const handleSite = useCallback(
    (nextSiteId: string) => {
      const resolved = resolveKnowledgeSiteId(sites, nextSiteId, siteId)
      if (resolved === null) {
        return
      }
      selectSite(resolved)
    },
    [selectSite, siteId, sites],
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
    urls,
    setSources,
    handleSite,
    ...sourceHandlers,
    ...pageHandlers,
  }
}
