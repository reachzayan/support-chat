"use client"

import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react"

import {
  staffRead,
  type KbPageDetail,
  type KbPageRecord,
  type KbSourceRecord,
  type SiteRecord,
} from "@/components/admin/staff-api"
import { useSearchTarget } from "@/components/search/workspace-route"
import { toast } from "@/components/ui/toast"

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
  const target = useSearchTarget()
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [siteId, setSiteId] = useState("")
  const [loadError, setLoadError] = useState<string | null>(null)
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
          setLoadError("Knowledge could not be loaded")
          return
        }
        const payload = (await response.json()) as { items: SiteRecord[] }
        setLoadError(null)
        setSites(payload.items)
        if (target.site && !payload.items.some((site) => site.id === target.site)) {
          setLoadError("This website is no longer available")
          return
        }
        if (payload.items[0]) {
          setSiteId(
            payload.items.find((site) => site.id === target.site)?.id ?? payload.items[0].id,
          )
        }
      } catch {
        if (request !== retryNonce) {
          return
        }
        setLoadError("Knowledge could not be loaded")
      }
    }
    void load()
  }, [retryNonce, target.site])

  const handleSite = useCallback((nextSiteId: string) => {
    setSiteId(nextSiteId)
  }, [])

  const handleRetryLoad = useCallback(() => {
    setRetryNonce((current) => current + 1)
  }, [])

  return { sites, siteId, handleSite, loadError, handleRetryLoad }
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
  const target = useSearchTarget()
  const [sources, setSources] = useState<KbSourceRecord[]>([])
  const [sourceId, setSourceId] = useState<string | null>(null)
  const [loadedSiteId, setLoadedSiteId] = useState("")
  const siteIdRef = useRef(siteId)
  const searchSourceApplied = useRef(false)

  const loadSources = useCallback(async () => {
    const currentSiteId = siteIdRef.current
    if (!currentSiteId) {
      return
    }
    const response = await staffRead(`/api/sites/${currentSiteId}/kb-sources`)
    if (siteIdRef.current !== currentSiteId) {
      return
    }
    if (!response.ok) {
      setLoadedSiteId(currentSiteId)
      return
    }
    const payload = (await response.json()) as { items: KbSourceRecord[] }
    if (siteIdRef.current !== currentSiteId) {
      return
    }
    applySourceList(payload.items, setSources, setSourceId)
    setLoadedSiteId(currentSiteId)
    if (!searchSourceApplied.current) {
      searchSourceApplied.current = true
      if (target.source && payload.items.some((source) => source.id === target.source))
        setSourceId(target.source)
    }
  }, [target.source])

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

  const sourcesLoaded = siteId !== "" && loadedSiteId === siteId

  return { sources, sourceId, sourcesLoaded, setSources, setSourceId, resetForSite }
}

const preferredKnowledgePage = (
  pages: KbPageRecord[],
  selectedId: string | null,
  target: Readonly<Record<string, string>>,
) => {
  const selected = pages.find((page) => page.id === selectedId)
  if (selected) return selected
  if (target.page) return pages.find((page) => page.id === target.page)
  if (target.source) return pages.find((page) => page.source_id === target.source)
  return pages[0]
}

const useKnowledgePages = (sources: KbSourceRecord[]) => {
  const target = useSearchTarget()
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
      const next = preferredKnowledgePage(visible, selectedId, target)
      if (next === undefined) {
        if (target.page)
          toast.add({ title: "This knowledge page is no longer available", type: "warning" })
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
  }, [pageRefreshKey, target])

  const resetPages = useCallback(() => {
    setPages([])
    setPageDetail(null)
  }, [])

  return { pages, pageDetail, setPages, setPageDetail, resetPages }
}

export const useKnowledgeCatalog = (isAdmin: boolean) => {
  const [urls, setUrls] = useState("")
  const { sites, siteId, handleSite: selectSite, loadError, handleRetryLoad } = useKnowledgeSites()
  const { sources, sourceId, sourcesLoaded, setSources, setSourceId } = useKnowledgeSources(siteId)
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
    sourcesLoaded,
    pages,
    pageDetail,
    urls,
    setSources,
    handleSite,
    loadError,
    handleRetryLoad,
    ...sourceHandlers,
    ...pageHandlers,
  }
}
