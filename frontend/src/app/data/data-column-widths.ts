"use client"

import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent } from "react"

import {
  clampWidth,
  DEFAULT_WIDTHS,
  readStoredWidths,
  WIDTH_STEP,
  WIDTHS_KEY,
  type ColumnLabel,
} from "./data-shared"

export const useDataColumnWidths = () => {
  const [widths, setWidths] = useState(readStoredWidths)
  const drag = useRef<{ label: ColumnLabel; startX: number; startWidth: number } | null>(null)

  const persistWidths = useCallback((next: Record<ColumnLabel, number>) => {
    window.localStorage.setItem(WIDTHS_KEY, JSON.stringify(next))
  }, [])

  const handleResizeStart = useCallback(
    (label: ColumnLabel, event: PointerEvent<HTMLButtonElement>) => {
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)
      drag.current = { label, startX: event.clientX, startWidth: widths[label] }
    },
    [widths],
  )

  const handleResizeMove = useCallback((event: PointerEvent<HTMLButtonElement>) => {
    const active = drag.current
    if (active === null) {
      return
    }
    const nextWidth = clampWidth(active.startWidth + event.clientX - active.startX)
    setWidths((current) => {
      if (current[active.label] === nextWidth) {
        return current
      }
      return { ...current, [active.label]: nextWidth }
    })
  }, [])

  const handleResizeEnd = useCallback(() => {
    if (drag.current === null) {
      return
    }
    drag.current = null
    setWidths((current) => {
      persistWidths(current)
      return current
    })
  }, [persistWidths])

  const handleResizeKeyDown = useCallback(
    (label: ColumnLabel, event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
        return
      }
      event.preventDefault()
      const delta = event.key === "ArrowRight" ? WIDTH_STEP : -WIDTH_STEP
      setWidths((current) => {
        const next = { ...current, [label]: clampWidth(current[label] + delta) }
        persistWidths(next)
        return next
      })
    },
    [persistWidths],
  )

  const handleResizeReset = useCallback(
    (label: ColumnLabel) => {
      setWidths((current) => {
        const next = { ...current, [label]: DEFAULT_WIDTHS[label] }
        persistWidths(next)
        return next
      })
    },
    [persistWidths],
  )

  const tableWidth = Object.values(widths).reduce((sum, value) => sum + value, 0)

  return {
    widths,
    tableWidth,
    handleResizeStart,
    handleResizeMove,
    handleResizeEnd,
    handleResizeKeyDown,
    handleResizeReset,
  }
}
