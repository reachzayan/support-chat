"use client"

import { Popover as PopoverPrimitive } from "@base-ui/react/popover"
import { cn } from "cn"

const Popover = PopoverPrimitive.Root
const PopoverTrigger = PopoverPrimitive.Trigger
const PopoverTitle = PopoverPrimitive.Title
const PopoverDescription = PopoverPrimitive.Description

const PopoverContent = ({
  className,
  children,
  positionerProps,
  ...props
}: PopoverPrimitive.Popup.Props & { positionerProps?: PopoverPrimitive.Positioner.Props }) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Positioner sideOffset={8} className="z-50" {...positionerProps}>
      <PopoverPrimitive.Popup
        className={cn(
          "border-line bg-paper text-ink w-[min(24rem,calc(100vw-2rem))] origin-(--transform-origin) rounded-[10px] border shadow-[0_12px_32px_rgba(13,31,58,0.18)] transition-[opacity,scale] duration-[180ms] data-ending-style:scale-[0.98] data-ending-style:opacity-0 data-starting-style:scale-[0.98] data-starting-style:opacity-0",
          className,
        )}
        {...props}
      >
        {children}
      </PopoverPrimitive.Popup>
    </PopoverPrimitive.Positioner>
  </PopoverPrimitive.Portal>
)

export { Popover, PopoverContent, PopoverTrigger, PopoverTitle, PopoverDescription }
