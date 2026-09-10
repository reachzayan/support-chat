"use client"

import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent } from "react"

import {
  COLUMNS,
  clampWidth,
  DEFAULT_WIDTHS,
  readStoredWidths,
  WIDTH_STEP,
  WIDTHS_KEY,
  type ColumnLabel,
} from "./sites-shared"

export const useSitesColumnWidths = () => {
  const [widths, setWidths] = useState<Record<ColumnLabel, number>>(readStoredWidths)
  const drag = useRef<{
    label: ColumnLabel
    startX: number
    startWidth: number
  } | null>(null)

  const persistWidths = useCallback((next: Record<ColumnLabel, number>) => {
    window.localStorage.setItem(WIDTHS_KEY, JSON.stringify(next))
  }, [])

  const handleResizeStart = useCallback(
    (label: ColumnLabel, event: PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      const startX = event.clientX
      const startWidth = widths[label]
      drag.current = { label, startX, startWidth }

      const handleMove = (moveEvent: globalThis.PointerEvent) => {
        if (drag.current === null || moveEvent.buttons === 0) {
          return
        }
        const deltaUnits = (moveEvent.clientX - startX) / 12
        const nextWidth = clampWidth(startWidth + deltaUnits)
        setWidths((current) => {
          if (current[label] === nextWidth) {
            return current
          }
          return { ...current, [label]: nextWidth }
        })
      }

      const handleUp = () => {
        window.removeEventListener("pointermove", handleMove)
        window.removeEventListener("pointerup", handleUp)
        window.removeEventListener("pointercancel", handleUp)
        drag.current = null
        setWidths((current) => {
          persistWidths(current)
          return current
        })
      }

      window.addEventListener("pointermove", handleMove)
      window.addEventListener("pointerup", handleUp)
      window.addEventListener("pointercancel", handleUp)
    },
    [persistWidths, widths],
  )

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

  const total = COLUMNS.reduce((sum, label) => sum + widths[label], 0)

  return { widths, total, handleResizeStart, handleResizeKeyDown, handleResizeReset }
}
