"use client"

/* oxlint-disable react-perf/jsx-no-new-object-as-prop -- Pane width is a live pixel value; a shared object would not stay in sync with drag. */

import { cn } from "cn"
import { motion, useReducedMotion } from "motion/react"
import { useCallback, type KeyboardEvent, type PointerEvent, type ReactNode } from "react"

import { Button } from "@/components/ui/button"

type PaneResizeHandleProps = {
  label: string
  width: number
  min: number
  max: number
  onResizeStart: (event: PointerEvent<HTMLButtonElement>) => void
  onResizeKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void
  onResizeReset: () => void
}

export const PaneResizeHandle = ({
  label,
  width,
  min,
  max,
  onResizeStart,
  onResizeKeyDown,
  onResizeReset,
}: PaneResizeHandleProps) => {
  const handleReset = useCallback(() => onResizeReset(), [onResizeReset])
  return (
    <Button
      type="button"
      variant="ghost"
      aria-label={`Resize ${label}`}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={width}
      title="Drag to resize. Arrow keys adjust. Double-click resets."
      onPointerDown={onResizeStart}
      onKeyDown={onResizeKeyDown}
      onDoubleClick={handleReset}
      className="pane-resize focus-visible:ring-steel absolute top-0 right-0 z-10 hidden h-full w-3 cursor-col-resize touch-none border-0 bg-transparent p-0 hover:bg-transparent focus-visible:ring-2 focus-visible:outline-none lg:block dark:hover:bg-transparent"
    />
  )
}

const PANE_WIDTH_INSTANT = { duration: 0 } as const
const PANE_WIDTH_EASE = { duration: 0.18, ease: [0.22, 1, 0.36, 1] } as const

type ResizableListPaneProps = {
  label: string
  width: number
  min: number
  max: number
  dragging: boolean
  className: string
  children: ReactNode
  onResizeStart: (event: PointerEvent<HTMLButtonElement>) => void
  onResizeKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void
  onResizeReset: () => void
}

export const ResizableListPane = ({
  label,
  width,
  min,
  max,
  dragging,
  className,
  children,
  onResizeStart,
  onResizeKeyDown,
  onResizeReset,
}: ResizableListPaneProps) => {
  const reducedMotion = useReducedMotion()
  const transition = dragging || reducedMotion ? PANE_WIDTH_INSTANT : PANE_WIDTH_EASE
  return (
    <motion.section
      initial={false}
      animate={{ width }}
      transition={transition}
      className={cn(
        "relative max-lg:!w-full lg:shrink-0 transition-[border-color] duration-150",
        "has-[.pane-resize:hover]:border-ink has-[.pane-resize:focus-visible]:border-ink",
        className,
      )}
    >
      {children}
      <PaneResizeHandle
        label={label}
        width={width}
        min={min}
        max={max}
        onResizeStart={onResizeStart}
        onResizeKeyDown={onResizeKeyDown}
        onResizeReset={onResizeReset}
      />
    </motion.section>
  )
}
