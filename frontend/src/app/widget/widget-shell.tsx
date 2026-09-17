/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

"use client"

import { Maximize2, Minimize2, RotateCcw, X } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import {
  useCallback,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type SyntheticEvent,
} from "react"

import {
  WIDGET_DEFAULT_HEIGHT,
  WIDGET_DEFAULT_WIDTH,
  WIDGET_EXPANDED_HEIGHT,
  WIDGET_EXPANDED_WIDTH,
} from "@/lib/postmessage"

const FOCUSABLE = "button, a[href], input, select, textarea"

const trapTab = (event: KeyboardEvent<HTMLDialogElement>) => {
  if (event.key !== "Tab") {
    return
  }
  const nodes = [...event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)]
  if (nodes.length === 0) {
    return
  }
  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  const active = event.currentTarget.ownerDocument.activeElement
  if (event.shiftKey && active === first) {
    event.preventDefault()
    last?.focus()
    return
  }
  if (!event.shiftKey && active === last) {
    event.preventDefault()
    first?.focus()
  }
}

export type WidgetSize = {
  width: number
  height: number
}

type WidgetShellProps = {
  name: string
  onClose: () => void
  onReset: () => void
  onResize?: (size: WidgetSize) => void
  children: ReactNode
}

const ICON_BUTTON =
  "bg-white/75 text-ink shadow-[0_6px_20px_rgba(13,31,58,0.10)] backdrop-blur-xl hover:bg-white hover:shadow-[0_10px_24px_rgba(13,31,58,0.14)] focus-visible:ring-steel flex size-10 cursor-pointer items-center justify-center rounded-full transition-[background-color,box-shadow,transform] duration-200 ease-out focus-visible:ring-2 focus-visible:outline-none active:scale-95"

export const WidgetShell = ({ name, onClose, onReset, onResize, children }: WidgetShellProps) => {
  const displayName =
    name
      .replace(/\bdemo\b/gi, "")
      .replace(/\s{2,}/g, " ")
      .trim() || "SupportChat"
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDialogElement>) => {
      if (event.key === "Escape") {
        event.preventDefault()
        onClose()
        return
      }
      trapTab(event)
    },
    [onClose],
  )
  const handleCancel = useCallback(
    (event: SyntheticEvent<HTMLDialogElement>) => {
      event.preventDefault()
      onClose()
    },
    [onClose],
  )

  return (
    <dialog
      open
      aria-label={displayName}
      onKeyDown={handleKeyDown}
      onCancel={handleCancel}
      className="widget-enter text-ink m-0 flex h-dvh max-h-none w-full max-w-none flex-col overflow-hidden rounded-[30px] border border-white/70 bg-white/78 p-0 font-sans shadow-[0_24px_70px_rgba(13,31,58,0.20)] backdrop-blur-2xl outline-none"
    >
      <header className="relative z-10 px-3 pt-3 pb-2">
        <WidgetTopbar name={displayName} onClose={onClose} onReset={onReset} onResize={onResize} />
      </header>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</main>
      <footer className="text-mute flex items-center justify-center px-4 pt-1 pb-3 text-center">
        <p className="rounded-full bg-white/65 px-3 py-1 text-[11px] leading-4 shadow-[0_4px_16px_rgba(13,31,58,0.05)] backdrop-blur-lg">
          AI responses may be incorrect. Do not share sensitive information.
        </p>
      </footer>
    </dialog>
  )
}

const WidgetTopbar = ({
  name,
  onClose,
  onReset,
  onResize,
}: {
  name: string
  onClose: () => void
  onReset: () => void
  onResize?: (size: WidgetSize) => void
}) => {
  const reducedMotion = useReducedMotion()

  return (
    <motion.div
      layout
      transition={reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }}
      className="grid grid-cols-[2.5rem_minmax(0,1fr)_auto] items-start gap-2"
    >
      <div>{onResize ? <ResizeHandle onResize={onResize} /> : null}</div>
      <motion.div
        layout="position"
        transition={
          reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }
        }
        className="mx-auto max-w-[240px] min-w-0 rounded-[22px] bg-white/80 px-4 py-2 shadow-[0_10px_28px_rgba(13,31,58,0.13)] backdrop-blur-xl"
      >
        <div className="min-w-0 text-center">
          <h1 className="heading truncate text-sm">{name}</h1>
          <p className="text-mute mt-0.5 text-[11px] font-medium whitespace-nowrap">
            Secure, assisted support
          </p>
        </div>
      </motion.div>
      <div className="flex items-center gap-1">
        <button type="button" aria-label="Reset chat" onClick={onReset} className={ICON_BUTTON}>
          <RotateCcw aria-hidden="true" className="size-[18px]" strokeWidth={2.2} />
        </button>
        <button type="button" aria-label="Close chat" onClick={onClose} className={ICON_BUTTON}>
          <X aria-hidden="true" className="size-5" strokeWidth={2.4} />
        </button>
      </div>
    </motion.div>
  )
}

const ResizeHandle = ({ onResize }: { onResize: (size: WidgetSize) => void }) => {
  const [expanded, setExpanded] = useState(false)
  const reducedMotion = useReducedMotion()
  const handleToggle = useCallback(() => {
    setExpanded((current) => {
      const next = !current
      onResize(
        next
          ? { width: WIDGET_EXPANDED_WIDTH, height: WIDGET_EXPANDED_HEIGHT }
          : { width: WIDGET_DEFAULT_WIDTH, height: WIDGET_DEFAULT_HEIGHT },
      )
      return next
    })
  }, [onResize])

  return (
    <button
      type="button"
      aria-label={expanded ? "Shrink chat" : "Expand chat"}
      aria-pressed={expanded}
      onClick={handleToggle}
      className={ICON_BUTTON}
    >
      <motion.span
        animate={{ rotate: expanded ? 180 : 0, scale: expanded ? 0.92 : 1 }}
        transition={
          reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 28 }
        }
        className="flex"
      >
        {expanded ? (
          <Minimize2 aria-hidden="true" className="size-[18px]" strokeWidth={2.2} />
        ) : (
          <Maximize2 aria-hidden="true" className="size-[18px]" strokeWidth={2.2} />
        )}
      </motion.span>
    </button>
  )
}
