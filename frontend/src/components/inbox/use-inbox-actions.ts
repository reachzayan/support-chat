"use client"

import { useCallback, type Dispatch, type SetStateAction } from "react"

import { emptyLive, type InboxLive } from "./inbox-session"
import type { SocketApi } from "./inbox-socket"
import type { InboxFilter } from "./types"
import type { InboxRefs } from "./use-inbox-refs"

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
      if (refs.selectedRef.current !== null) {
        socketRef.current?.unsubscribe(refs.selectedRef.current)
      }
      refs.markSelected(id)
      setSelectedId(id)
      const nextLive = emptyLive()
      refs.resetLive(nextLive)
      setLive(nextLive)
      reloadDetail(id)
    },
    [refs, reloadDetail, setLive, setSelectedId, socketRef],
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
      if (refs.selectedRef.current !== null && socketRef.current !== null) {
        return socketRef.current.sendMessage(refs.selectedRef.current, crypto.randomUUID(), body)
      }
      return false
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
