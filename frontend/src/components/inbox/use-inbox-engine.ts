"use client"

import { useCallback, useEffect, useMemo, useRef, type Dispatch, type SetStateAction } from "react"

import { agentSocketUrl, createAgentSocket } from "@/lib/agent-ws"
import { getAccessToken, refreshSession } from "@/lib/auth-client"
import { createReconnectScheduler } from "@/lib/ws-reconnect"

import { fetchInboxDetail, fetchInboxList } from "./inbox-api"
import { applyAgentFrame, emptyLive, maxMessageId, type InboxLive } from "./inbox-session"
import {
  INBOX_LIST_POLL_MS,
  type CannedReply,
  type InboxCounts,
  type InboxFilter,
  type InboxListItem,
} from "./types"

export type SocketApi = ReturnType<typeof createAgentSocket>
type DetailBundle = NonNullable<Awaited<ReturnType<typeof fetchInboxDetail>>>

export type InboxRefs = {
  selectedRef: { current: string | null }
  lastIdRef: { current: number }
  filterRef: { current: InboxFilter }
  userRef: { current: string }
  liveRef: { current: InboxLive }
  markSelected: (id: string | null) => void
  markFilter: (filter: InboxFilter) => void
  resetLive: (live: InboxLive) => void
}

export const useInboxSyncRefs = (
  selectedId: string | null,
  live: InboxLive,
  filter: InboxFilter,
  userId: string,
): InboxRefs => {
  const selectedRef = useRef(selectedId)
  const lastIdRef = useRef(0)
  const filterRef = useRef(filter)
  const userRef = useRef(userId)
  const liveRef = useRef(live)
  const markSelected = useCallback((id: string | null) => {
    selectedRef.current = id
  }, [])
  const markFilter = useCallback((nextFilter: InboxFilter) => {
    filterRef.current = nextFilter
  }, [])
  const resetLive = useCallback((nextLive: InboxLive) => {
    liveRef.current = nextLive
  }, [])
  const refs = useMemo(
    () => ({
      selectedRef,
      lastIdRef,
      filterRef,
      userRef,
      liveRef,
      markSelected,
      markFilter,
      resetLive,
    }),
    [selectedRef, lastIdRef, filterRef, userRef, liveRef, markSelected, markFilter, resetLive],
  )
  useEffect(() => {
    selectedRef.current = selectedId
  }, [selectedId])
  useEffect(() => {
    lastIdRef.current = maxMessageId(live.lines)
  }, [live.lines])
  useEffect(() => {
    filterRef.current = filter
  }, [filter])
  useEffect(() => {
    userRef.current = userId
  }, [userId])
  useEffect(() => {
    liveRef.current = live
  }, [live])
  return refs
}

type AgentScheduler = ReturnType<typeof createReconnectScheduler>

const bindAgentSocket = (
  refs: InboxRefs,
  setLive: (live: InboxLive) => void,
  reloadList: (filter: InboxFilter) => void,
  reloadDetail: (id: string) => void,
  scheduler: AgentScheduler,
) => {
  const socket = createAgentSocket({
    url: agentSocketUrl(),
    accessToken: getAccessToken() ?? "",
    onFrame: (frame) => {
      scheduler.markAuthenticated()
      const effect = applyAgentFrame(
        refs.liveRef.current,
        frame,
        refs.userRef.current,
        refs.selectedRef.current,
      )
      refs.liveRef.current = effect.live
      setLive(effect.live)
      if (effect.refetchList) {
        reloadList(refs.filterRef.current)
      }
      if (effect.refetchDetailId !== null) {
        reloadDetail(effect.refetchDetailId)
      }
    },
    onClose: (code) => {
      void handleAgentSocketClose(code, socket, refs, scheduler)
    },
  })
  return socket
}

const resumeAgentSocket = (socket: SocketApi, refs: InboxRefs) => {
  socket.reconnect()
  if (refs.selectedRef.current !== null) {
    socket.subscribe(refs.selectedRef.current, refs.lastIdRef.current)
  }
  socket.flushUnacked()
}

const handleAgentSocketClose = async (
  code: number,
  socket: SocketApi,
  refs: InboxRefs,
  scheduler: AgentScheduler,
) => {
  if (code === 1000 || code === 4403) {
    return
  }
  if (code === 4401) {
    const user = await refreshSession()
    if (user === null) {
      return
    }
    socket.setAccessToken(getAccessToken() ?? "")
    scheduler.markAuthenticated()
    resumeAgentSocket(socket, refs)
    return
  }
  scheduler.handleClose()
}

const applyFetchedDetail = (
  conversationId: string,
  next: DetailBundle,
  userId: string,
  lastIdRef: { current: number },
  socketRef: { current: SocketApi | null },
  setCanned: (canned: CannedReply[]) => void,
  setLive: (live: InboxLive) => void,
) => {
  const assigned = next.detail.assigned_agent
  const winner = assigned && assigned.id !== userId ? assigned.display_name : null
  setCanned(next.canned)
  lastIdRef.current = maxMessageId(next.detail.messages)
  socketRef.current?.subscribe(conversationId, lastIdRef.current)
  setLive({
    chatState: next.detail.state,
    assigned,
    joinPending: false,
    winnerName: winner,
    detail: next.detail,
    lines: next.detail.messages,
  })
}

const mergeInboxPages = async (filter: InboxFilter, extraCursors: string[]) => {
  const first = await fetchInboxList(filter)
  if (first === null) {
    return null
  }
  const pages = await Promise.all(extraCursors.map((extra) => fetchInboxList(filter, extra)))
  const items = [...first.items]
  let nextCursor = first.next_cursor
  let counts = first.counts
  for (const page of pages) {
    if (page === null) {
      return { items, nextCursor, counts }
    }
    items.push(...page.items)
    nextCursor = page.next_cursor
    counts = page.counts
  }
  return { items, nextCursor, counts }
}

type InboxListReloadRefs = {
  listGenerationRef: { current: number }
  extraCursorsRef: { current: string[] }
  loadedCursorsRef: { current: Set<string> }
  filterRef: { current: InboxFilter }
}

const runInboxListReload = async (
  nextFilter: InboxFilter,
  cursor: string | null | undefined,
  reloadRefs: InboxListReloadRefs,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
) => {
  const generation = reloadRefs.listGenerationRef.current
  if (cursor) {
    if (reloadRefs.loadedCursorsRef.current.has(cursor)) {
      return
    }
    reloadRefs.loadedCursorsRef.current.add(cursor)
    reloadRefs.extraCursorsRef.current.push(cursor)
    const next = await fetchInboxList(nextFilter, cursor)
    if (
      next === null ||
      generation !== reloadRefs.listGenerationRef.current ||
      reloadRefs.filterRef.current !== nextFilter
    ) {
      reloadRefs.loadedCursorsRef.current.delete(cursor)
      return
    }
    setItems((current) => {
      const seen = new Set(current.map((item) => item.id))
      const fresh = next.items.filter((item) => !seen.has(item.id))
      return [...current, ...fresh]
    })
    setNextCursor(next.next_cursor)
    setCounts(next.counts)
    return
  }
  const merged = await mergeInboxPages(nextFilter, reloadRefs.extraCursorsRef.current)
  if (
    merged === null ||
    generation !== reloadRefs.listGenerationRef.current ||
    reloadRefs.filterRef.current !== nextFilter
  ) {
    return
  }
  const unique = merged.items.filter(
    (item, index, items) => items.findIndex((row) => row.id === item.id) === index,
  )
  setItems(unique)
  setNextCursor(merged.nextCursor)
  setCounts(merged.counts)
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
        {
          listGenerationRef,
          extraCursorsRef,
          loadedCursorsRef,
          filterRef: refs.filterRef,
        },
        setItems,
        setNextCursor,
        setCounts,
      )
    },
    [refs.filterRef, setCounts, setItems, setNextCursor],
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

export const useInboxSideEffects = (
  filter: InboxFilter,
  refs: InboxRefs,
  socketRef: { current: SocketApi | null },
  reloadList: (filter: InboxFilter) => void,
  reloadDetail: (id: string) => void,
  clearLoadedCursors: () => void,
  setItems: Dispatch<SetStateAction<InboxListItem[]>>,
  setLive: Dispatch<SetStateAction<InboxLive>>,
  setNextCursor: Dispatch<SetStateAction<string | null>>,
  setCounts: Dispatch<SetStateAction<InboxCounts>>,
) => {
  useEffect(() => {
    let cancelled = false
    clearLoadedCursors()
    const load = async () => {
      const next = await fetchInboxList(filter)
      if (!cancelled && next !== null && refs.filterRef.current === filter) {
        setItems(next.items)
        setNextCursor(next.next_cursor)
        setCounts(next.counts)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [clearLoadedCursors, filter, refs.filterRef, setCounts, setItems, setNextCursor])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) {
        reloadList(refs.filterRef.current)
        if (refs.selectedRef.current !== null) {
          reloadDetail(refs.selectedRef.current)
        }
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
      if (!document.hidden && navigator.onLine) {
        scheduler.handleClose()
      }
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

export const useInboxActions = (
  refs: InboxRefs,
  socketRef: { current: SocketApi | null },
  setSelectedId: Dispatch<SetStateAction<string | null>>,
  setLive: Dispatch<SetStateAction<InboxLive>>,
  reloadDetail: (id: string) => void,
  reloadList: (filter: InboxFilter, cursor?: string | null) => void,
) => {
  const handleSelect = useCallback(
    (id: string) => {
      if (refs.selectedRef.current === id && refs.liveRef.current.detail?.id === id) {
        return
      }
      refs.markSelected(id)
      setSelectedId(id)
      const nextLive = emptyLive()
      refs.resetLive(nextLive)
      setLive(nextLive)
      reloadDetail(id)
    },
    [refs, reloadDetail, setLive, setSelectedId],
  )
  const handleJoin = useCallback(() => {
    if (refs.selectedRef.current === null) {
      return
    }
    setLive((current) => ({ ...current, joinPending: true }))
    socketRef.current?.join(refs.selectedRef.current)
  }, [refs.selectedRef, setLive, socketRef])
  const handleMarkContacted = useCallback(() => {
    if (refs.selectedRef.current !== null) {
      socketRef.current?.closeAttention(refs.selectedRef.current)
    }
  }, [refs.selectedRef, socketRef])
  const handleEnd = useCallback(() => {
    if (refs.selectedRef.current !== null) {
      socketRef.current?.end(refs.selectedRef.current)
    }
  }, [refs.selectedRef, socketRef])
  const handleTransfer = useCallback(() => {
    if (refs.selectedRef.current !== null) {
      socketRef.current?.transferToBot(refs.selectedRef.current)
    }
  }, [refs.selectedRef, socketRef])
  const handleSend = useCallback(
    (body: string) => {
      if (refs.selectedRef.current !== null) {
        socketRef.current?.sendMessage(refs.selectedRef.current, crypto.randomUUID(), body)
      }
    },
    [refs.selectedRef, socketRef],
  )
  const handleLoadMore = useCallback(
    (cursor: string) => {
      reloadList(refs.filterRef.current, cursor)
    },
    [refs.filterRef, reloadList],
  )
  return {
    handleSelect,
    handleJoin,
    handleMarkContacted,
    handleEnd,
    handleTransfer,
    handleSend,
    handleLoadMore,
  }
}
