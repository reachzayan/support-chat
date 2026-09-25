"use client"

import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from "react"

import { fetchInboxDetailPage, mergeInboxMessages } from "./inbox-api"
import { emptyLive, type InboxLive } from "./inbox-session"
import { EMPTY_INBOX_COUNTS, type CannedReply, type InboxFilter, type InboxListItem } from "./types"
import {
  useInboxActions,
  useInboxLoaders,
  useInboxSideEffects,
  useInboxSyncRefs,
  type InboxRefs,
  type SocketApi,
} from "./use-inbox-engine"

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

export const useInboxLive = (userId: string) => {
  const [filter, setFilter] = useState<InboxFilter>("human")
  const [items, setItems] = useState<InboxListItem[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [live, setLive] = useState(emptyLive)
  const [canned, setCanned] = useState<CannedReply[]>([])
  const [counts, setCounts] = useState(EMPTY_INBOX_COUNTS)
  const socketRef = useRef<SocketApi | null>(null)
  const refs = useInboxSyncRefs(selectedId, live, filter, userId)
  const { reloadList, reloadDetail, clearLoadedCursors } = useInboxLoaders(
    refs,
    socketRef,
    setItems,
    setCanned,
    setLive,
    setNextCursor,
    setCounts,
  )
  useInboxSideEffects(
    filter,
    refs,
    socketRef,
    reloadList,
    reloadDetail,
    clearLoadedCursors,
    setItems,
    setLive,
    setNextCursor,
    setCounts,
  )
  const actions = useInboxActions(refs, socketRef, setSelectedId, setLive, reloadDetail, reloadList)
  const olderMessages = useOlderMessages(refs, setLive)
  const handleFilter = useCallback(
    (nextFilter: InboxFilter) => {
      if (nextFilter === filter) {
        return
      }
      refs.markFilter(nextFilter)
      refs.markSelected(null)
      const nextLive = emptyLive()
      refs.resetLive(nextLive)
      setFilter(nextFilter)
      setSelectedId(null)
      setLive(nextLive)
    },
    [filter, refs, setLive, setSelectedId],
  )
  return {
    filter,
    setFilter: handleFilter,
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
