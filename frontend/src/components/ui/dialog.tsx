/* oxlint-disable react-perf/jsx-no-jsx-as-prop */

"use client"

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { cn } from "cn"
import { XIcon } from "lucide-react"
import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react"
import * as React from "react"
import { useLayoutEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"

const DIALOG_RESIZE_TRANSITION = { duration: 0.2, ease: [0.23, 1, 0.32, 1] } as const
const REDUCED_MOTION_TRANSITION = { duration: 0 } as const

const DIALOG_FRAME =
  "border-line bg-paper text-ink pointer-events-auto relative isolate z-50 flex max-h-[min(92vh,48rem)] w-[calc(100%-2rem)] max-w-lg flex-col overflow-hidden rounded-card border shadow-[0_16px_48px_rgba(13,31,58,0.22)] transition-[opacity,scale] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] data-ending-style:scale-[0.97] data-ending-style:opacity-0 data-starting-style:scale-[0.97] data-starting-style:opacity-0"

const Dialog = ({ ...props }: DialogPrimitive.Root.Props) => {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

const DialogPortal = ({ ...props }: DialogPrimitive.Portal.Props) => {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

const DialogOverlay = ({ className, ...props }: DialogPrimitive.Backdrop.Props) => {
  return (
    <DialogPrimitive.Backdrop
      data-slot="dialog-overlay"
      className={cn(
        "bg-navy/40 fixed inset-0 z-50 transition-opacity duration-200 ease-out data-ending-style:opacity-0 data-starting-style:opacity-0 dark:bg-black/60",
        className,
      )}
      {...props}
    />
  )
}

const DialogContent = ({
  className,
  children,
  showCloseButton = true,
  ...props
}: DialogPrimitive.Popup.Props & {
  showCloseButton?: boolean
}) => {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Viewport
        data-slot="dialog-viewport"
        className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <DialogPrimitive.Popup
          data-slot="dialog-content"
          className={cn(DIALOG_FRAME, className)}
          {...props}
        >
          {children}
          {showCloseButton ? (
            <DialogPrimitive.Close
              data-slot="dialog-close"
              render={
                <Button
                  variant="ghost"
                  className="absolute top-3 right-3"
                  size="icon-sm"
                  aria-label="Close dialog"
                />
              }
            >
              <XIcon aria-hidden="true" />
            </DialogPrimitive.Close>
          ) : null}
        </DialogPrimitive.Popup>
      </DialogPrimitive.Viewport>
    </DialogPortal>
  )
}

// Fixed dialogs ignore layout animations; measure inner content and tween height instead.
const DialogResizeSection = ({
  className,
  children,
  ...props
}: Omit<HTMLMotionProps<"div">, "children"> & { children: React.ReactNode }) => {
  const reducedMotion = useReducedMotion()
  const measureRef = useRef<HTMLDivElement>(null)
  const [height, setHeight] = useState<number | "auto">("auto")

  useLayoutEffect(() => {
    const node = measureRef.current
    if (!node) {
      return
    }
    const updateHeight = () => {
      setHeight(node.offsetHeight)
    }
    updateHeight()
    if (typeof ResizeObserver === "undefined") {
      return
    }
    const observer = new ResizeObserver(updateHeight)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <motion.div
      // oxlint-disable-next-line react-perf/jsx-no-new-object-as-prop -- motion.div animate requires a height object
      animate={{ height }}
      initial={false}
      transition={reducedMotion ? REDUCED_MOTION_TRANSITION : DIALOG_RESIZE_TRANSITION}
      className="min-h-0 overflow-x-hidden overflow-y-auto overscroll-none"
      {...props}
    >
      <div ref={measureRef} className={cn(className)}>
        {children}
      </div>
    </motion.div>
  )
}

const DialogHeader = ({ className, ...props }: React.ComponentProps<"div">) => {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex shrink-0 flex-col gap-1 border-b border-line px-5 py-4 pr-12", className)}
      {...props}
    />
  )
}

const DialogFooter = ({ className, ...props }: React.ComponentProps<"div">) => {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "border-line bg-paper sticky bottom-0 z-10 mt-auto flex shrink-0 flex-col items-center gap-2 border-t px-5 py-4",
        className,
      )}
      {...props}
    />
  )
}

const DialogTitle = ({ className, ...props }: DialogPrimitive.Title.Props) => {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-navy heading text-base", className)}
      {...props}
    />
  )
}

const DialogDescription = ({ className, ...props }: DialogPrimitive.Description.Props) => {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-mute text-xs", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogResizeSection,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
