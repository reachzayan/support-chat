"use client"

import { cn } from "cn"
import { useCallback, useMemo, useState, type ReactNode } from "react"

type CollapsibleProps = {
  defaultOpen?: boolean
  children: ReactNode
  className?: string
}

type CollapsibleContextValue = {
  open: boolean
  setOpen: (open: boolean) => void
}

import { createContext, useContext } from "react"

const CollapsibleContext = createContext<CollapsibleContextValue | null>(null)

const Collapsible = ({ defaultOpen = false, children, className }: CollapsibleProps) => {
  const [open, setOpen] = useState(defaultOpen)
  const contextValue = useMemo(() => ({ open, setOpen }), [open])
  return (
    <CollapsibleContext.Provider value={contextValue}>
      <div data-slot="collapsible" className={className}>
        {children}
      </div>
    </CollapsibleContext.Provider>
  )
}

const CollapsibleTrigger = ({ className, children, ...props }: React.ComponentProps<"button">) => {
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

const CollapsibleContent = ({ className, children, ...props }: React.ComponentProps<"div">) => {
  const ctx = useContext(CollapsibleContext)
  if (ctx === null || !ctx.open) {
    return null
  }
  return (
    <div data-slot="collapsible-content" className={cn("mt-2", className)} {...props}>
      {children}
    </div>
  )
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
