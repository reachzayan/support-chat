"use client"

import { Maximize2, Minimize2, RotateCcw, X } from "lucide-react"
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
  "text-paper/85 hover:bg-white/10 hover:text-paper focus-visible:ring-paper flex size-9 cursor-pointer items-center justify-center rounded-[8px] transition-colors duration-150 focus-visible:ring-2 focus-visible:outline-none"

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
      className="widget-enter bg-paper text-ink m-0 flex h-dvh max-h-none w-full max-w-none flex-col overflow-hidden rounded-[18px] border-0 p-0 font-sans"
    >
      <header className="border-navy-mid bg-navy text-paper border-b px-5 py-4">
        <WidgetTopbar name={displayName} onClose={onClose} onReset={onReset} onResize={onResize} />
      </header>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</main>
      <footer className="border-line text-mute bg-paper flex items-center justify-center border-t px-5 py-3 text-center">
        <p className="text-[11px] leading-4">
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
  return (
    <div className="relative flex items-center justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-extrabold tracking-[-0.025em]">{name}</h1>
          <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-white/65">
            <span className="bg-ember-soft size-1.5 rounded-full" aria-hidden="true" />
            Secure, assisted support
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1">
        {onResize ? <ResizeHandle onResize={onResize} /> : null}
        <button type="button" aria-label="Reset chat" onClick={onReset} className={ICON_BUTTON}>
          <RotateCcw aria-hidden="true" className="size-5" strokeWidth={2.2} />
        </button>
        <button type="button" aria-label="Close chat" onClick={onClose} className={ICON_BUTTON}>
          <X aria-hidden="true" className="size-6" strokeWidth={2.2} />
        </button>
      </div>
    </div>
  )
}

const ResizeHandle = ({ onResize }: { onResize: (size: WidgetSize) => void }) => {
  const [expanded, setExpanded] = useState(false)
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
      {expanded ? (
        <Minimize2
          aria-hidden="true"
          className="size-5 transition-transform duration-200 ease-out"
          strokeWidth={2.2}
        />
      ) : (
        <Maximize2
          aria-hidden="true"
          className="size-5 transition-transform duration-200 ease-out"
          strokeWidth={2.2}
        />
      )}
    </button>
  )
}
