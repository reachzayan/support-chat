/* oxlint-disable react-perf/jsx-no-new-object-as-prop */
/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- Base UI composes shadcn buttons through render. */
/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- menu callbacks are local UI state */
/* oxlint-disable max-lines-per-function -- menu and confirmations form one keyboard interaction */

"use client"

import { RotateCcw, Trash2 } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type SyntheticEvent,
} from "react"

import {
  AlertDialog,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { StateIcon } from "@/components/ui/state-icon"
import {
  WIDGET_DEFAULT_HEIGHT,
  WIDGET_DEFAULT_WIDTH,
  WIDGET_EXPANDED_HEIGHT,
  WIDGET_EXPANDED_WIDTH,
} from "@/lib/postmessage"

import { WidgetSoundOption } from "./widget-sound-option"

const FOCUSABLE = "button, a[href], input, select, textarea"

const trapTab = (event: KeyboardEvent<HTMLDialogElement>) => {
  if (event.key !== "Tab") {
    return
  }
  const nodes = [...event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (node) => !node.closest("[hidden]"),
  )
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
  /** True when the host shows the widget as a full-viewport sheet (phones). */
  fullscreen?: boolean
  /** Hide the generic footer when the screen already carries its own disclaimer. */
  hideDisclaimer?: boolean
  onClose: () => void
  onResetCurrent: () => void
  onDeleteAll: () => void
  onResize?: (size: WidgetSize) => void
  children: ReactNode
}

const ICON_BUTTON =
  "text-ink focus-visible:ring-steel flex size-11 cursor-pointer items-center justify-center rounded-full transition-transform duration-200 ease-out focus-visible:ring-2 focus-visible:outline-none active:scale-95"

const SHELL_BASE =
  "text-ink m-0 flex max-h-none w-full max-w-none flex-col overflow-hidden p-0 font-sans outline-none"
const SHELL_PANEL = "h-dvh rounded-[30px] border border-white/70 bg-white/78 backdrop-blur-2xl"
const SHELL_SHEET =
  "h-dvh rounded-none border-0 bg-white pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)]"

export const WidgetLoading = ({ fullscreen = false }: { fullscreen?: boolean }) => (
  <output
    aria-label="Loading chat"
    className={`${SHELL_BASE} ${fullscreen ? SHELL_SHEET : SHELL_PANEL}`}
  >
    <div className="flex items-center gap-3 px-4 pt-4 pb-2" aria-hidden="true">
      <div className="bg-navy size-9 shrink-0 rounded-full" />
      <div className="skeleton-shimmer bg-ice-2 h-4 w-32 rounded-full" />
    </div>
    <div className="flex flex-1 flex-col gap-3 px-5 py-4" aria-hidden="true">
      <div className="skeleton-shimmer bg-ice-2 h-11 rounded-lg" />
      <div className="skeleton-shimmer bg-ice-2 h-11 w-4/5 rounded-lg" />
      <div className="skeleton-shimmer bg-ice-2 h-11 w-3/5 rounded-lg" />
    </div>
    <span className="sr-only">Loading chat…</span>
  </output>
)

export const WidgetShell = ({
  name,
  fullscreen = false,
  hideDisclaimer = false,
  onClose,
  onResetCurrent,
  onDeleteAll,
  onResize,
  children,
}: WidgetShellProps) => {
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
      data-layout={fullscreen ? "sheet" : "panel"}
      className={`widget-enter ${SHELL_BASE} ${fullscreen ? SHELL_SHEET : SHELL_PANEL}`}
    >
      <header className="relative z-10 px-3 pt-2 pb-2 sm:pt-3">
        <WidgetTopbar
          name={displayName}
          onClose={onClose}
          onResetCurrent={onResetCurrent}
          onDeleteAll={onDeleteAll}
          onResize={fullscreen ? undefined : onResize}
          fullscreen={fullscreen}
        />
      </header>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</main>
      {hideDisclaimer ? null : (
        <footer className="text-mute flex items-center justify-center px-4 pt-1 pb-2 text-center sm:pb-3">
          <p className="rounded-full bg-white/65 px-3 py-1 text-[11px] leading-4 backdrop-blur-lg">
            AI responses may be incorrect. Do not share sensitive information.
          </p>
        </footer>
      )}
    </dialog>
  )
}

const WidgetTopbar = ({
  name,
  onClose,
  onResetCurrent,
  onDeleteAll,
  onResize,
  fullscreen,
}: {
  name: string
  onClose: () => void
  onResetCurrent: () => void
  onDeleteAll: () => void
  onResize?: (size: WidgetSize) => void
  fullscreen: boolean
}) => {
  const reducedMotion = useReducedMotion()

  return (
    <motion.div
      layout
      transition={reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }}
      className={
        fullscreen
          ? "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2"
          : "grid grid-cols-[2.75rem_minmax(0,1fr)_auto] items-start gap-2"
      }
    >
      {fullscreen ? null : <div>{onResize ? <ResizeHandle onResize={onResize} /> : null}</div>}
      <motion.div
        layout="position"
        transition={
          reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }
        }
        className={
          fullscreen
            ? "min-w-0 px-2 py-1"
            : "mx-auto max-w-[240px] min-w-0 rounded-[22px] bg-white/80 px-4 py-2 backdrop-blur-xl"
        }
      >
        <div className={fullscreen ? "min-w-0 text-left" : "min-w-0 text-center"}>
          <h1 className="heading truncate text-sm">{name}</h1>
          <p className="text-mute mt-0.5 text-[11px] font-medium whitespace-nowrap">
            Secure, assisted support
          </p>
        </div>
      </motion.div>
      <div className="flex items-center gap-1">
        <ConversationMenu onResetCurrent={onResetCurrent} onDeleteAll={onDeleteAll} />
        <Button
          type="button"
          variant="ghost"
          aria-label="Close chat"
          onClick={onClose}
          className={ICON_BUTTON}
          size="icon"
        >
          <StateIcon name="x" className="size-5" />
        </Button>
      </div>
    </motion.div>
  )
}

const MENU_ITEM =
  "text-ink data-highlighted:bg-ice flex min-h-11 cursor-pointer items-center gap-2.5 px-3 text-sm font-semibold outline-none data-highlighted:text-navy"
const DIALOG_BUTTON =
  "focus-visible:ring-steel min-h-11 px-4 text-sm font-bold leading-none focus-visible:ring-2 focus-visible:outline-none"

const ConversationMenu = ({
  onResetCurrent,
  onDeleteAll,
}: {
  onResetCurrent: () => void
  onDeleteAll: () => void
}) => {
  const [confirmation, setConfirmation] = useState<"reset" | "delete" | null>(null)
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const firstItemRef = useRef<HTMLButtonElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (open) firstItemRef.current?.focus()
  }, [open])
  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("pointerdown", closeOutside)
    return () => document.removeEventListener("pointerdown", closeOutside)
  }, [open])
  const closeMenu = () => {
    setOpen(false)
    queueMicrotask(() => triggerRef.current?.focus())
  }
  return (
    <>
      <div ref={containerRef} className="relative">
        <Button
          ref={triggerRef}
          type="button"
          variant="ghost"
          aria-label="More options"
          aria-haspopup="menu"
          aria-expanded={open}
          className={ICON_BUTTON}
          size="icon"
          onClick={() => setOpen((current) => !current)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault()
              setOpen(true)
            }
          }}
        >
          <StateIcon name="dots-three" className="size-5" />
        </Button>
        <div hidden={!open}>
          <div
            role="menu"
            tabIndex={-1}
            aria-label="Chat options"
            className="border-line bg-paper absolute top-12 right-0 z-40 w-52 overflow-hidden rounded-2xl border py-1.5 shadow-[0_18px_48px_rgba(13,31,58,0.20)] outline-none"
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault()
                event.stopPropagation()
                closeMenu()
                return
              }
              if (event.key === "Tab") {
                setOpen(false)
                return
              }
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault()
                const items = [
                  ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    '[role="menuitem"], [role="menuitemcheckbox"]',
                  ),
                ]
                const current = items.indexOf(event.target as HTMLButtonElement)
                const change = event.key === "ArrowDown" ? 1 : -1
                items[(current + change + items.length) % items.length]?.focus()
              }
            }}
          >
            <WidgetSoundOption className={`${MENU_ITEM} w-full`} />
            <Button
              ref={firstItemRef}
              type="button"
              variant="ghost"
              role="menuitem"
              className={`${MENU_ITEM} w-full`}
              onClick={() => {
                setOpen(false)
                setConfirmation("reset")
              }}
            >
              <RotateCcw aria-hidden="true" className="size-4" />
              Reset current chat
            </Button>
            <Button
              type="button"
              variant="ghost"
              role="menuitem"
              className={`${MENU_ITEM} w-full text-red-700 data-highlighted:text-red-800`}
              onClick={() => {
                setOpen(false)
                setConfirmation("delete")
              }}
            >
              <Trash2 aria-hidden="true" className="size-4" />
              Delete all chats
            </Button>
          </div>
        </div>
      </div>
      <AlertDialog
        open={confirmation !== null}
        onOpenChange={(dialogOpen) => {
          if (!dialogOpen) {
            setConfirmation(null)
            queueMicrotask(() => triggerRef.current?.focus())
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmation === "delete"
                ? "Delete all chats from this browser?"
                : "Reset current chat?"}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-mute mt-2 text-sm leading-5">
              {confirmation === "delete"
                ? "This removes access to your chat history from this browser. Retained support records are not erased."
                : "This chat will close and stay saved in your chat history. A new chat will open."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogClose render={<Button variant="outline" className={DIALOG_BUTTON} />}>
              Cancel
            </AlertDialogClose>
            <AlertDialogClose
              render={<Button variant="default" className={DIALOG_BUTTON} />}
              onClick={confirmation === "delete" ? onDeleteAll : onResetCurrent}
            >
              {confirmation === "delete" ? "Delete all chats" : "Reset chat"}
            </AlertDialogClose>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
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
    <Button
      type="button"
      variant="ghost"
      aria-label={expanded ? "Shrink chat" : "Expand chat"}
      aria-pressed={expanded}
      onClick={handleToggle}
      className={ICON_BUTTON}
      size="icon"
    >
      <motion.span
        animate={{ rotate: expanded ? 180 : 0, scale: expanded ? 0.92 : 1 }}
        transition={
          reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 28 }
        }
        className="flex"
      >
        {expanded ? (
          <StateIcon name="arrows-in-simple" className="size-[18px]" />
        ) : (
          <StateIcon name="arrows-out-simple" className="size-[18px]" />
        )}
      </motion.span>
    </Button>
  )
}
