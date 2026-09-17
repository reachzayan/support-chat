/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

"use client"

import { cn } from "cn"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react"

type CollapsibleProps = {
  defaultOpen?: boolean
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: ReactNode
  className?: string
}

type CollapsibleContextValue = {
  open: boolean
  setOpen: (open: boolean) => void
}

const CollapsibleContext = createContext<CollapsibleContextValue | null>(null)

const Collapsible = ({
  defaultOpen = false,
  open: openProp,
  onOpenChange,
  children,
  className,
}: CollapsibleProps) => {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen)
  const isControlled = openProp !== undefined
  const open = isControlled ? openProp : uncontrolledOpen
  const setOpen = useCallback(
    (next: boolean) => {
      if (!isControlled) {
        setUncontrolledOpen(next)
      }
      onOpenChange?.(next)
    },
    [isControlled, onOpenChange],
  )
  const contextValue = useMemo(() => ({ open, setOpen }), [open, setOpen])
  return (
    <CollapsibleContext.Provider value={contextValue}>
      <div data-slot="collapsible" className={className}>
        {children}
      </div>
    </CollapsibleContext.Provider>
  )
}

const CollapsibleTrigger = ({ className, children, ...props }: ComponentProps<"button">) => {
  const ctx = useContext(CollapsibleContext)
  const handleToggle = useCallback(() => {
    ctx?.setOpen(!(ctx?.open ?? false))
  }, [ctx])
  if (ctx === null) {
    return null
  }
  return (
    <button
      type="button"
      data-slot="collapsible-trigger"
      aria-expanded={ctx.open}
      onClick={handleToggle}
      className={cn(
        "text-navy focus-visible:ring-steel flex w-full items-center justify-between text-left text-sm font-bold focus-visible:ring-2 focus-visible:outline-none",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

// Quiet, functional motion: height + opacity only, matching the theme's 150-200ms guidance.
const COLLAPSE_TRANSITION = { duration: 0.2, ease: [0.23, 1, 0.32, 1] } as const

const CollapsibleContent = ({ className, children, ...props }: ComponentProps<"div">) => {
  const ctx = useContext(CollapsibleContext)
  const reducedMotion = useReducedMotion()
  if (ctx === null) {
    return null
  }
  const transition = reducedMotion ? { duration: 0 } : COLLAPSE_TRANSITION
  return (
    <AnimatePresence initial={false}>
      {ctx.open ? (
        <motion.div
          key="collapsible-content"
          data-slot="collapsible-content-frame"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={transition}
          className="overflow-hidden"
        >
          <div data-slot="collapsible-content" className={cn("mt-2", className)} {...props}>
            {children}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
