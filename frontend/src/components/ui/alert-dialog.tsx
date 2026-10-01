"use client"

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { cn } from "cn"
import * as React from "react"

const AlertDialog = DialogPrimitive.Root
const AlertDialogTrigger = DialogPrimitive.Trigger
const AlertDialogClose = DialogPrimitive.Close
const AlertDialogTitle = ({ className, ...props }: DialogPrimitive.Title.Props) => (
  <DialogPrimitive.Title className={cn("text-navy heading text-base", className)} {...props} />
)
const AlertDialogDescription = DialogPrimitive.Description

const ALERT_FRAME =
  "border-line bg-paper text-ink pointer-events-auto isolate z-50 flex max-h-[min(92vh,48rem)] w-[calc(100%-2rem)] max-w-md flex-col overflow-hidden rounded-card border shadow-[0_16px_48px_rgba(13,31,58,0.22)] transition-[opacity,scale] duration-200 data-ending-style:scale-[0.97] data-ending-style:opacity-0 data-starting-style:scale-[0.97] data-starting-style:opacity-0"

const AlertDialogContent = ({ className, children, ...props }: DialogPrimitive.Popup.Props) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Backdrop
      data-slot="dialog-overlay"
      className="bg-navy/40 fixed inset-0 z-50 transition-opacity duration-200 data-ending-style:opacity-0 data-starting-style:opacity-0"
    />
    <DialogPrimitive.Viewport className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4">
      <DialogPrimitive.Popup className={cn(ALERT_FRAME, className)} {...props}>
        {children}
      </DialogPrimitive.Popup>
    </DialogPrimitive.Viewport>
  </DialogPrimitive.Portal>
)

const AlertDialogHeader = ({ className, ...props }: React.ComponentProps<"div">) => (
  <div className={cn("flex shrink-0 flex-col gap-1 px-5 pt-5", className)} {...props} />
)

const AlertDialogFooter = ({ className, ...props }: React.ComponentProps<"div">) => (
  <div
    className={cn(
      "bg-paper sticky bottom-0 z-10 mt-5 flex shrink-0 justify-end gap-2 border-t border-line px-5 py-4",
      className,
    )}
    {...props}
  />
)

export {
  AlertDialog,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
}
