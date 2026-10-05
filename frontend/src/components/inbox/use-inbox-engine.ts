"use client"

import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from "react"

import { createReconnectScheduler } from "@/lib/ws-reconnect"

import { fetchInboxDetail, fetchInboxList, mergeInboxMessages } from "./inbox-api"
import { maxMessageId, type InboxLive } from "./inbox-session"
import { bindAgentSocket, resumeAgentSocket, type SocketApi } from "./inbox-socket"
import {
  INBOX_LIST_POLL_MS,
  type CannedReply,
  type InboxCounts,
  type InboxFilter,
  type InboxListItem,
  type InboxSite,
} from "./types"
import type { InboxRefs } from "./use-inbox-refs"

type DetailBundle = NonNullable<Awaited<ReturnType<typeof fetchInboxDetail>>>

const applyFetchedDetail = (
  conversationId: string,
  next: DetailBundle,
  userId: string,
  lastIdRef: { current: number },
  liveRef: { current: InboxLive },
  socketRef: { current: SocketApi | null },
  setCanned: (canned: CannedReply[]) => void,
  setLive: (live: InboxLive) => void,
) => {
  const assigned = next.detail.assigned_agent
  const winner = assigned && assigned.id !== userId ? assigned.display_name : null
  const previous = liveRef.current.detail?.id === conversationId ? liveRef.current.detail : null
  const lines = previous
    ? mergeInboxMessages(previous.messages, next.detail.messages)
    : next.detail.messages
  const detail = previous
    ? {
        ...next.detail,
        messages: lines,
        has_older: previous.has_older,
        older_before_id: previous.older_before_id,
      }
    : next.detail
  const nextLive: InboxLive = {
    chatState: detail.state,
    assigned,
    joinPending: false,
    winnerName: winner,
    detail,
    lines,
  }
  liveRef.current = nextLive
  setCanned(next.canned)
  lastIdRef.current = maxMessageId(lines)
  setLive(nextLive)
  socketRef.current?.subscribe(conversationId, lastIdRef.current)
}

const mergeInboxPages = async (
  filter: InboxFilter,
  extraCursors: string[],
  siteId: string | null,
) => {
  const first = await fetchInboxList(filter, null, siteId)
  if (first === null || first === "invalid_site") {
    return first
  }
  const pages = await Promise.all(
    extraCursors.map((extra) => fetchInboxList(filter, extra, siteId)),
  )
  const items = [...first.items]
  let nextCursor = first.next_cursor
  let counts = first.counts
  let sites = first.sites
  for (const page of pages) {
    if (page === null || page === "invalid_site") {
      return { items, nextCursor, counts, sites }
    }
    items.push(...page.items)
    nextCursor = page.next_cursor
    counts = page.counts
    sites = page.sites
  }
  return { items, nextCursor, counts, sites }
}

type InboxListReloadRefs = {
  listGenerationRef: { current: number }
  extraCursorsRef: { current: string[] }
  loadedCursorsRef: { current: Set<string> }
  filterRef: { current: InboxFilter }
  siteIdRef: { current: string | null }
}

const isCurrentListQuery = (
  reloadRefs: InboxListReloadRefs,
  generation: number,
  nextFilter: InboxFilter,
  siteId: string | null,
) => {
  return (
    generation === reloadRefs.listGenerationRef.current &&
    reloadRefs.filterRef.current === nextFilter &&
    reloadRefs.siteIdRef.current === siteId
  )
}

const isInboxListFailure = (next: object | null | "invalid_site"): next is null | "invalid_site" =>
  next === null || next === "invalid_site"

const applyInboxListFailure = (
  next: null | "invalid_site",
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  if (next === "invalid_site") {
    onUnknownSite()
    return
  }
  setLoadError(true)
}

const appendInboxCursorPage = async (
  nextFilter: InboxFilter,
  cursor: string,
  siteId: string | null,
  generation: number,
  reloadRefs: InboxListReloadRefs,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
  setSites: Dispatch<SetStateAction<InboxSite[]>>,
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  if (reloadRefs.loadedCursorsRef.current.has(cursor)) {
    return
  }
  reloadRefs.loadedCursorsRef.current.add(cursor)
  reloadRefs.extraCursorsRef.current.push(cursor)
  const next = await fetchInboxList(nextFilter, cursor, siteId)
  if (isInboxListFailure(next) || !isCurrentListQuery(reloadRefs, generation, nextFilter, siteId)) {
    reloadRefs.loadedCursorsRef.current.delete(cursor)
    if (isInboxListFailure(next)) {
      applyInboxListFailure(next, setLoadError, onUnknownSite)
    }
    return
  }
  setLoadError(false)
  setItems((current) => {
    const seen = new Set(current.map((item) => item.id))
    const fresh = next.items.filter((item) => !seen.has(item.id))
    return [...current, ...fresh]
  })
  setNextCursor(next.next_cursor)
  setCounts(next.counts)
  setSites(next.sites)
}

const replaceInboxMergedPages = async (
  nextFilter: InboxFilter,
  siteId: string | null,
  generation: number,
  reloadRefs: InboxListReloadRefs,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
  setSites: Dispatch<SetStateAction<InboxSite[]>>,
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  const merged = await mergeInboxPages(nextFilter, reloadRefs.extraCursorsRef.current, siteId)
  if (
    isInboxListFailure(merged) ||
    !isCurrentListQuery(reloadRefs, generation, nextFilter, siteId)
  ) {
    if (isInboxListFailure(merged)) {
      applyInboxListFailure(merged, setLoadError, onUnknownSite)
    }
    return
  }
  const unique = merged.items.filter(
    (item, index, items) => items.findIndex((row) => row.id === item.id) === index,
  )
  setLoadError(false)
  setItems(unique)
  setNextCursor(merged.nextCursor)
  setCounts(merged.counts)
  setSites(merged.sites)
}

const runInboxListReload = async (
  nextFilter: InboxFilter,
  cursor: string | null | undefined,
  siteId: string | null,
  reloadRefs: InboxListReloadRefs,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
  setSites: Dispatch<SetStateAction<InboxSite[]>>,
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  const generation = reloadRefs.listGenerationRef.current
  if (cursor) {
    await appendInboxCursorPage(
      nextFilter,
      cursor,
      siteId,
      generation,
      reloadRefs,
      setItems,
      setNextCursor,
      setCounts,
      setSites,
      setLoadError,
      onUnknownSite,
    )
    return
  }
  await replaceInboxMergedPages(
    nextFilter,
    siteId,
    generation,
    reloadRefs,
    setItems,
    setNextCursor,
    setCounts,
    setSites,
    setLoadError,
    onUnknownSite,
  )
}

const loadInboxDetail = async (
  conversationId: string,
  request: number,
  detailRequestRef: { current: number },
  refs: InboxRefs,
  socketRef: { current: SocketApi | null },
  setCanned: Dispatch<SetStateAction<CannedReply[]>>,
  setLive: Dispatch<SetStateAction<InboxLive>>,
) => {
  const next = await fetchInboxDetail(conversationId)
  if (
    next === null ||
    request !== detailRequestRef.current ||
    refs.selectedRef.current !== conversationId
  ) {
    return
  }
  applyFetchedDetail(
    conversationId,
    next,
    refs.userRef.current,
    refs.lastIdRef,
    refs.liveRef,
    socketRef,
    setCanned,
    setLive,
  )
}

export const useInboxLoaders = (
  refs: InboxRefs,
  socketRef: { current: SocketApi | null },
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setCanned: Dispatch<SetStateAction<CannedReply[]>>,
  setLive: Dispatch<SetStateAction<InboxLive>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
  setSites: Dispatch<SetStateAction<InboxSite[]>>,
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  const extraCursorsRef = useRef<string[]>([])
  const loadedCursorsRef = useRef<Set<string>>(new Set())
  const listGenerationRef = useRef(0)
  const detailRequestRef = useRef(0)
  const clearLoadedCursors = useCallback(() => {
    extraCursorsRef.current = []
    loadedCursorsRef.current = new Set()
    listGenerationRef.current += 1
    detailRequestRef.current += 1
  }, [])
  const reloadList = useCallback(
    (nextFilter: InboxFilter, cursor?: string | null) => {
      void runInboxListReload(
        nextFilter,
        cursor,
        refs.siteIdRef.current,
        {
          listGenerationRef,
          extraCursorsRef,
          loadedCursorsRef,
          filterRef: refs.filterRef,
          siteIdRef: refs.siteIdRef,
        },
        setItems,
        setNextCursor,
        setCounts,
        setSites,
        setLoadError,
        onUnknownSite,
      )
    },
    [
      onUnknownSite,
      refs.filterRef,
      refs.siteIdRef,
      setCounts,
      setItems,
      setLoadError,
      setNextCursor,
      setSites,
    ],
  )

  const reloadDetail = useCallback(
    (conversationId: string) => {
      const request = ++detailRequestRef.current
      void loadInboxDetail(
        conversationId,
        request,
        detailRequestRef,
        refs,
        socketRef,
        setCanned,
        setLive,
      )
    },
    [refs, setCanned, setLive, socketRef],
  )

  return { reloadList, reloadDetail, clearLoadedCursors }
}

const useInboxListFetch = (
  filter: InboxFilter,
  siteId: string | null,
  refs: InboxRefs,
  clearLoadedCursors: () => void,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
  setSites: Dispatch<SetStateAction<InboxSite[]>>,
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  useEffect(() => {
    let cancelled = false
    clearLoadedCursors()
    const load = async () => {
      const next = await fetchInboxList(filter, null, siteId)
      if (cancelled || refs.filterRef.current !== filter || refs.siteIdRef.current !== siteId) {
        return
      }
      if (next === "invalid_site") {
        onUnknownSite()
        return
      }
      if (next === null) {
        setLoadError(true)
        return
      }
      if (siteId !== null && !next.sites.some((site) => site.id === siteId)) {
        onUnknownSite()
        return
      }
      setLoadError(false)
      setItems(next.items)
      setNextCursor(next.next_cursor)
      setCounts(next.counts)
      setSites(next.sites)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [
    clearLoadedCursors,
    filter,
    onUnknownSite,
    refs.filterRef,
    refs.siteIdRef,
    setCounts,
    setItems,
    setLoadError,
    setNextCursor,
    setSites,
    siteId,
  ])
}

export const useInboxSideEffects = (
  filter: InboxFilter,
  siteId: string | null,
  refs: InboxRefs,
  socketRef: { current: SocketApi | null },
  reloadList: (filter: InboxFilter) => void,
  reloadDetail: (id: string) => void,
  clearLoadedCursors: () => void,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setLive: Dispatch<SetStateAction<InboxLive>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
  setSites: Dispatch<SetStateAction<InboxSite[]>>,
  setLoadError: Dispatch<SetStateAction<boolean>>,
  onUnknownSite: () => void,
) => {
  useInboxListFetch(
    filter,
    siteId,
    refs,
    clearLoadedCursors,
    setItems,
    setNextCursor,
    setCounts,
    setSites,
    setLoadError,
    onUnknownSite,
  )

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.hidden) {
        return
      }
      reloadList(refs.filterRef.current)
      if (refs.selectedRef.current !== null) {
        reloadDetail(refs.selectedRef.current)
      }
    }, INBOX_LIST_POLL_MS)
    return () => window.clearInterval(timer)
  }, [reloadDetail, reloadList, refs.filterRef, refs.selectedRef])

  useEffect(() => {
    let disposed = false
    const scheduler = createReconnectScheduler({
      onReconnect: () => {
        const socket = socketRef.current
        if (socket === null) {
          return
        }
        resumeAgentSocket(socket, refs)
      },
      isDisposed: () => disposed,
    })
    const socket = bindAgentSocket(refs, setLive, reloadList, reloadDetail, scheduler)
    socketRef.current = socket

    const handleResume = () => {
      if (document.hidden || !navigator.onLine) {
        return
      }
      if (socketRef.current?.isOpen()) {
        return
      }
      scheduler.handleClose()
    }
    window.addEventListener("online", handleResume)
    document.addEventListener("visibilitychange", handleResume)

    return () => {
      disposed = true
      scheduler.dispose()
      window.removeEventListener("online", handleResume)
      document.removeEventListener("visibilitychange", handleResume)
      socket.close()
      socketRef.current = null
    }
  }, [reloadDetail, reloadList, refs, setLive, socketRef])
}
