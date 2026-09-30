"use client"

import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent } from "react"

export const INBOX_LIST_WIDTH_KEY = "supportchat.inbox.list-width"
export const KNOWLEDGE_SOURCE_WIDTH_KEY = "supportchat.knowledge.source-width"
export const INBOX_SITE_KEY = "supportchat.inbox.site-id"

export const MIN_PANE_WIDTH = 280
export const MAX_PANE_WIDTH = 640
export const INBOX_LIST_DEFAULT_WIDTH = 360
export const KNOWLEDGE_SOURCE_DEFAULT_WIDTH = 448
export const PANE_WIDTH_STEP = 24

const SITE_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export const clampPaneWidth = (value: number) => {
  return Math.min(MAX_PANE_WIDTH, Math.max(MIN_PANE_WIDTH, Math.round(value)))
}

export const readStoredPaneWidth = (key: string, fallback: number) => {
  if (typeof window === "undefined") {
    return fallback
  }
  const raw = window.localStorage.getItem(key)
  if (raw === null || raw === "") {
    return fallback
  }
  const parsed = Number(raw)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return clampPaneWidth(parsed)
}

export const persistPaneWidth = (key: string, width: number) => {
  window.localStorage.setItem(key, String(width))
}

export const readStoredInboxSiteId = () => {
  if (typeof window === "undefined") {
    return null
  }
  const raw = window.localStorage.getItem(INBOX_SITE_KEY)
  if (raw === null || !SITE_ID_PATTERN.test(raw)) {
    return null
  }
  return raw
}

export const persistInboxSiteId = (siteId: string | null) => {
  if (siteId === null) {
    window.localStorage.removeItem(INBOX_SITE_KEY)
    return
  }
  window.localStorage.setItem(INBOX_SITE_KEY, siteId)
}

export const usePaneWidth = (storageKey: string, defaultWidth: number) => {
  const [width, setWidth] = useState(() => readStoredPaneWidth(storageKey, defaultWidth))
  const [dragging, setDragging] = useState(false)
  const drag = useRef<{ startX: number; startWidth: number } | null>(null)

  const persist = useCallback(
    (next: number) => {
      persistPaneWidth(storageKey, next)
    },
    [storageKey],
  )

  const handleResizeStart = useCallback(
    (event: PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      const startX = event.clientX
      const startWidth = width
      drag.current = { startX, startWidth }
      setDragging(true)

      const handleMove = (moveEvent: globalThis.PointerEvent) => {
        if (drag.current === null || moveEvent.buttons === 0) {
          return
        }
        const nextWidth = clampPaneWidth(startWidth + moveEvent.clientX - startX)
        setWidth((current) => (current === nextWidth ? current : nextWidth))
      }

      const handleUp = () => {
        window.removeEventListener("pointermove", handleMove)
        window.removeEventListener("pointerup", handleUp)
        window.removeEventListener("pointercancel", handleUp)
        drag.current = null
        setDragging(false)
        setWidth((current) => {
          persist(current)
          return current
        })
      }

      window.addEventListener("pointermove", handleMove)
      window.addEventListener("pointerup", handleUp)
      window.addEventListener("pointercancel", handleUp)
    },
    [persist, width],
  )

  const handleResizeKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
        return
      }
      event.preventDefault()
      const delta = event.key === "ArrowRight" ? PANE_WIDTH_STEP : -PANE_WIDTH_STEP
      setWidth((current) => {
        const next = clampPaneWidth(current + delta)
        persist(next)
        return next
      })
    },
    [persist],
  )

  const handleResizeReset = useCallback(() => {
    setWidth(defaultWidth)
    persist(defaultWidth)
  }, [defaultWidth, persist])

  return { width, dragging, handleResizeStart, handleResizeKeyDown, handleResizeReset }
}
