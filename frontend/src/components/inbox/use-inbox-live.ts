"use client"

import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from "react"

import { persistInboxSiteId, readStoredInboxSiteId } from "@/lib/pane-width"

import { fetchInboxDetailPage, mergeInboxMessages } from "./inbox-api"
import { emptyLive, type InboxLive } from "./inbox-session"
import type { SocketApi } from "./inbox-socket"
import {
  EMPTY_INBOX_COUNTS,
  type CannedReply,
  type InboxFilter,
  type InboxListItem,
  type InboxSite,
} from "./types"
import { useInboxActions } from "./use-inbox-actions"
import { useInboxLoaders, useInboxSideEffects } from "./use-inbox-engine"
import { useInboxSyncRefs, type InboxRefs } from "./use-inbox-refs"

const useOlderMessages = (refs: InboxRefs, setLive: Dispatch<SetStateAction<InboxLive>>) => {
  const [loadingOlder, setLoadingOlder] = useState(false)
  const handleLoadOlder = async () => {
    const detail = refs.liveRef.current.detail
    const beforeId = detail?.older_before_id
    if (detail === null || beforeId == null || loadingOlder) {
      return
    }
    const conversationId = detail.id
    setLoadingOlder(true)
    try {
      const older = await fetchInboxDetailPage(conversationId, beforeId)
      if (older === null || refs.selectedRef.current !== conversationId) {
        return
      }
      const latest = refs.liveRef.current
      if (latest.detail?.id !== conversationId) {
        return
      }
      const lines = mergeInboxMessages(older.messages, latest.lines)
      const nextLive = {
        ...latest,
        lines,
        detail: {
          ...latest.detail,
          messages: lines,
          has_older: older.has_older,
          older_before_id: older.older_before_id,
        },
      }
      refs.resetLive(nextLive)
      setLive(nextLive)
    } finally {
      setLoadingOlder(false)
    }
  }
  return { loadingOlder, handleLoadOlder }
}

const useInboxQueryHandlers = (
  refs: InboxRefs,
  socketRef: { current: SocketApi | null },
  filter: InboxFilter,
  siteId: string | null,
  setFilter: Dispatch<SetStateAction<InboxFilter>>,
  setSiteId: Dispatch<SetStateAction<string | null>>,
  setSelectedId: Dispatch<SetStateAction<string | null>>,
  setLive: Dispatch<SetStateAction<InboxLive>>,
) => {
  const clearOpenChat = useCallback(() => {
    if (refs.selectedRef.current !== null) {
      socketRef.current?.unsubscribe(refs.selectedRef.current)
    }
    refs.markSelected(null)
    const nextLive = emptyLive()
    refs.resetLive(nextLive)
    setSelectedId(null)
    setLive(nextLive)
  }, [refs, setLive, setSelectedId, socketRef])
  const handleFilter = useCallback(
    (nextFilter: InboxFilter) => {
      if (nextFilter === filter) {
        return
      }
      refs.markFilter(nextFilter)
      clearOpenChat()
      setFilter(nextFilter)
    },
    [clearOpenChat, filter, refs, setFilter],
  )
  const handleSite = useCallback(
    (nextSiteId: string | null) => {
      if (nextSiteId === siteId) {
        return
      }
      persistInboxSiteId(nextSiteId)
      refs.markSiteId(nextSiteId)
      clearOpenChat()
      setSiteId(nextSiteId)
    },
    [clearOpenChat, refs, setSiteId, siteId],
  )
  const handleUnknownSite = useCallback(() => {
    persistInboxSiteId(null)
    refs.markSiteId(null)
    setSiteId(null)
  }, [refs, setSiteId])
  return { handleFilter, handleSite, handleUnknownSite }
}

export const useInboxLive = (userId: string) => {
  const [filter, setFilter] = useState<InboxFilter>("human")
  const [siteId, setSiteId] = useState<string | null>(readStoredInboxSiteId)
  const [sites, setSites] = useState<InboxSite[]>([])
  const [loadError, setLoadError] = useState(false)
  const [items, setItems] = useState<InboxListItem[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [live, setLive] = useState(emptyLive)
  const [canned, setCanned] = useState<CannedReply[]>([])
  const [counts, setCounts] = useState(EMPTY_INBOX_COUNTS)
  const socketRef = useRef<SocketApi | null>(null)
  const refs = useInboxSyncRefs(selectedId, live, filter, siteId, userId)
  const query = useInboxQueryHandlers(
    refs,
    socketRef,
    filter,
    siteId,
    setFilter,
    setSiteId,
    setSelectedId,
    setLive,
  )
  const { reloadList, reloadDetail, clearLoadedCursors } = useInboxLoaders(
    refs,
    socketRef,
    setItems,
    setCanned,
    setLive,
    setNextCursor,
    setCounts,
    setSites,
    setLoadError,
    query.handleUnknownSite,
  )
  useInboxSideEffects(
    filter,
    siteId,
    refs,
    socketRef,
    reloadList,
    reloadDetail,
    clearLoadedCursors,
    setItems,
    setLive,
    setNextCursor,
    setCounts,
    setSites,
    setLoadError,
    query.handleUnknownSite,
  )
  const actions = useInboxActions(refs, socketRef, setSelectedId, setLive, reloadDetail, reloadList)
  const olderMessages = useOlderMessages(refs, setLive)
  const handleRetryLoad = useCallback(() => {
    setLoadError(false)
    reloadList(refs.filterRef.current)
  }, [refs.filterRef, reloadList])
  return {
    filter,
    setFilter: query.handleFilter,
    siteId,
    sites,
    setSite: query.handleSite,
    loadError,
    handleRetryLoad,
    items,
    nextCursor,
    selectedId,
    live,
    canned,
    counts,
    ...olderMessages,
    ...actions,
  }
}
