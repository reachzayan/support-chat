"use client"

import { useCallback, useEffect, useMemo, useRef } from "react"

import { maxMessageId, type InboxLive } from "./inbox-session"
import type { InboxFilter } from "./types"

export type InboxRefs = {
  selectedRef: { current: string | null }
  lastIdRef: { current: number }
  filterRef: { current: InboxFilter }
  siteIdRef: { current: string | null }
  userRef: { current: string }
  liveRef: { current: InboxLive }
  markSelected: (id: string | null) => void
  markFilter: (filter: InboxFilter) => void
  markSiteId: (siteId: string | null) => void
  resetLive: (live: InboxLive) => void
}

export const useInboxSyncRefs = (
  selectedId: string | null,
  live: InboxLive,
  filter: InboxFilter,
  siteId: string | null,
  userId: string,
): InboxRefs => {
  const selectedRef = useRef(selectedId)
  const lastIdRef = useRef(0)
  const filterRef = useRef(filter)
  const siteIdRef = useRef(siteId)
  const userRef = useRef(userId)
  const liveRef = useRef(live)
  const markSelected = useCallback((id: string | null) => {
    selectedRef.current = id
  }, [])
  const markFilter = useCallback((nextFilter: InboxFilter) => {
    filterRef.current = nextFilter
  }, [])
  const markSiteId = useCallback((nextSiteId: string | null) => {
    siteIdRef.current = nextSiteId
  }, [])
  const resetLive = useCallback((nextLive: InboxLive) => {
    liveRef.current = nextLive
  }, [])
  const refs = useMemo(
    () => ({
      selectedRef,
      lastIdRef,
      filterRef,
      siteIdRef,
      userRef,
      liveRef,
      markSelected,
      markFilter,
      markSiteId,
      resetLive,
    }),
    [
      selectedRef,
      lastIdRef,
      filterRef,
      siteIdRef,
      userRef,
      liveRef,
      markSelected,
      markFilter,
      markSiteId,
      resetLive,
    ],
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
    siteIdRef.current = siteId
  }, [siteId])
  useEffect(() => {
    userRef.current = userId
  }, [userId])
  useEffect(() => {
    if (live.detail === null && liveRef.current.detail !== null) {
      return
    }
    liveRef.current = live
  }, [live])
  return refs
}
