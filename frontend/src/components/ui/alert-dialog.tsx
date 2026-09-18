"use client"

import { AlertDialog as AlertDialogPrimitive } from "@base-ui/react/alert-dialog"
import { cn } from "cn"
import * as React from "react"

const AlertDialog = AlertDialogPrimitive.Root
const AlertDialogTrigger = AlertDialogPrimitive.Trigger
const AlertDialogClose = AlertDialogPrimitive.Close
const AlertDialogTitle = ({ className, ...props }: AlertDialogPrimitive.Title.Props) => (
  <AlertDialogPrimitive.Title className={cn("text-navy heading text-base", className)} {...props} />
)
const AlertDialogDescription = AlertDialogPrimitive.Description

const ALERT_FRAME =
  "border-line bg-paper text-ink pointer-events-auto isolate z-50 flex w-[calc(100%-2rem)] max-w-md flex-col overflow-hidden rounded-2xl border shadow-[0_16px_48px_rgba(13,31,58,0.22)] transition-[opacity,scale] duration-200 data-ending-style:scale-[0.97] data-ending-style:opacity-0 data-starting-style:scale-[0.97] data-starting-style:opacity-0"

const AlertDialogContent = ({
  className,
  children,
  ...props
}: AlertDialogPrimitive.Popup.Props) => (
  <AlertDialogPrimitive.Portal>
    <AlertDialogPrimitive.Backdrop className="bg-navy/40 fixed inset-0 z-50 transition-opacity duration-200 data-ending-style:opacity-0 data-starting-style:opacity-0" />
    <AlertDialogPrimitive.Viewport className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center p-4">
      <AlertDialogPrimitive.Popup className={cn(ALERT_FRAME, className)} {...props}>
        {children}
      </AlertDialogPrimitive.Popup>
    </AlertDialogPrimitive.Viewport>
  </AlertDialogPrimitive.Portal>
)

const AlertDialogHeader = ({ className, ...props }: React.ComponentProps<"div">) => (
  <div className={cn("flex flex-col gap-1 px-5 pt-5", className)} {...props} />
)

const AlertDialogFooter = ({ className, ...props }: React.ComponentProps<"div">) => (
  <div
    className={cn("mt-5 flex justify-end gap-2 border-t border-line px-5 py-4", className)}
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
