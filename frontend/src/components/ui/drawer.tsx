"use client"

import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer"
import { cn } from "cn"
import * as React from "react"

import { buttonVariants } from "@/components/ui/button"
import { StateIcon } from "@/components/ui/state-icon"

type Direction = NonNullable<DrawerPrimitive.Root.Props["swipeDirection"]>
const DrawerContext = React.createContext({
  direction: "down" as Direction,
  showSwipeHandle: false,
})

const DRAWER_SIDES = {
  left: "mr-auto h-full w-3/4 max-w-sm data-starting-style:[--drawer-enter-x:calc(-100%_-_1rem)] data-ending-style:[--drawer-enter-x:calc(-100%_-_1rem)]",
  right:
    "ml-auto h-full w-3/4 max-w-sm data-starting-style:[--drawer-enter-x:calc(100%_+_1rem)] data-ending-style:[--drawer-enter-x:calc(100%_+_1rem)]",
  up: "mb-auto max-h-[calc(100dvh-6rem)] w-full data-starting-style:[--drawer-enter-y:calc(-100%_-_1rem)] data-ending-style:[--drawer-enter-y:calc(-100%_-_1rem)]",
  down: "mt-auto max-h-[calc(100dvh-6rem)] w-full data-starting-style:[--drawer-enter-y:calc(100%_+_1rem)] data-ending-style:[--drawer-enter-y:calc(100%_+_1rem)]",
} as const

function Drawer({
  swipeDirection = "down",
  showSwipeHandle = false,
  ...props
}: DrawerPrimitive.Root.Props & { showSwipeHandle?: boolean }) {
  const context = React.useMemo(
    () => ({ direction: swipeDirection, showSwipeHandle }),
    [swipeDirection, showSwipeHandle],
  )
  return (
    <DrawerContext.Provider value={context}>
      <DrawerPrimitive.Root swipeDirection={swipeDirection} {...props} />
    </DrawerContext.Provider>
  )
}

function DrawerTrigger(props: DrawerPrimitive.Trigger.Props) {
  return <DrawerPrimitive.Trigger data-slot="drawer-trigger" {...props} />
}

function DrawerClose(props: DrawerPrimitive.Close.Props) {
  return <DrawerPrimitive.Close data-slot="drawer-close" {...props} />
}

function DrawerPortal(props: DrawerPrimitive.Portal.Props) {
  return <DrawerPrimitive.Portal {...props} />
}

function DrawerOverlay({ className, ...props }: DrawerPrimitive.Backdrop.Props) {
  return (
    <DrawerPrimitive.Backdrop
      data-slot="drawer-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-navy/35 [opacity:calc(1-var(--drawer-swipe-progress,0))] transition-opacity duration-150 data-starting-style:opacity-0 data-ending-style:opacity-0 data-swiping:transition-none motion-reduce:transition-none",
        className,
      )}
      {...props}
    />
  )
}

function DrawerSwipeHandle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      aria-hidden="true"
      data-slot="drawer-swipe-handle"
      className={cn(
        "bg-muted-foreground/30 mx-auto my-3 h-1 w-10 shrink-0 rounded-full group-data-[swipe-axis=x]/drawer-popup:hidden",
        className,
      )}
      {...props}
    />
  )
}

function DrawerContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: DrawerPrimitive.Popup.Props & { showCloseButton?: boolean }) {
  const { direction, showSwipeHandle } = React.useContext(DrawerContext)
  const axis = direction === "left" || direction === "right" ? "x" : "y"
  return (
    <DrawerPortal>
      <DrawerOverlay />
      <DrawerPrimitive.Viewport className="pointer-events-none fixed inset-0 z-50 flex pt-[max(0.5rem,env(safe-area-inset-top))] pr-[max(0.5rem,env(safe-area-inset-right))] pb-[max(0.5rem,env(safe-area-inset-bottom))] pl-[max(0.5rem,env(safe-area-inset-left))]">
        <DrawerPrimitive.Popup
          data-slot="drawer-content"
          data-swipe-axis={axis}
          className={cn(
            "group/drawer-popup bg-popover text-popover-foreground pointer-events-auto relative flex min-h-0 flex-col overflow-hidden rounded-lg border border-line bg-clip-padding text-sm shadow-xl outline-none [translate:calc(var(--drawer-swipe-movement-x,0px)+var(--drawer-enter-x,0px))_calc(var(--drawer-swipe-movement-y,0px)+var(--drawer-snap-point-offset,0px)+var(--drawer-enter-y,0px))] [transition:translate_calc(200ms*var(--drawer-swipe-strength,1))_cubic-bezier(0.22,1,0.36,1)] data-swiping:transition-none motion-reduce:transition-none",
            DRAWER_SIDES[direction],
            className,
          )}
          {...props}
        >
          {showSwipeHandle ? <DrawerSwipeHandle /> : null}
          <DrawerPrimitive.Content className="flex min-h-0 flex-1 flex-col">
            {children}
          </DrawerPrimitive.Content>
          {showCloseButton ? (
            <DrawerClose
              aria-label="Close panel"
              className={cn(
                buttonVariants({ variant: "ghost", size: "icon" }),
                "absolute top-2 right-2 size-11 text-current hover:text-current",
              )}
            >
              <StateIcon name="x" className="size-5" />
            </DrawerClose>
          ) : null}
        </DrawerPrimitive.Popup>
      </DrawerPrimitive.Viewport>
    </DrawerPortal>
  )
}

function DrawerHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="drawer-header"
      className={cn(
        "flex min-h-16 shrink-0 flex-col justify-center gap-1 border-b border-line px-5 py-4 pr-16",
        className,
      )}
      {...props}
    />
  )
}

function DrawerFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="drawer-footer"
      className={cn("mt-auto flex shrink-0 flex-col gap-2 border-t border-line p-4", className)}
      {...props}
    />
  )
}

function DrawerTitle({ className, ...props }: DrawerPrimitive.Title.Props) {
  return (
    <DrawerPrimitive.Title
      data-slot="drawer-title"
      className={cn("heading text-base text-foreground", className)}
      {...props}
    />
  )
}

function DrawerDescription({ className, ...props }: DrawerPrimitive.Description.Props) {
  return (
    <DrawerPrimitive.Description
      data-slot="drawer-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Drawer,
  DrawerTrigger,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
  DrawerPortal,
  DrawerOverlay,
  DrawerSwipeHandle,
}
