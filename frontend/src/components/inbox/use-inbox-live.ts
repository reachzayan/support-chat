"use client"

import { useRef, useState } from "react"

import { emptyLive } from "./inbox-session"
import { EMPTY_INBOX_COUNTS, type CannedReply, type InboxFilter, type InboxListItem } from "./types"
import {
  useInboxActions,
  useInboxLoaders,
  useInboxSideEffects,
  useInboxSyncRefs,
  type SocketApi,
} from "./use-inbox-engine"

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
  return { filter, setFilter, items, nextCursor, selectedId, live, canned, counts, ...actions }
}
