"use client"

import { Switch as SwitchPrimitive } from "@base-ui/react/switch"
import { cn } from "cn"

const Switch = ({ className, children, ...props }: SwitchPrimitive.Root.Props) => (
  <SwitchPrimitive.Root
    data-slot="switch"
    className={cn(
      "focus-visible:ring-steel inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-full bg-line p-0.5 transition-[background-color,box-shadow] duration-150 ease-out data-checked:bg-steel focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60",
      className,
    )}
    {...props}
  >
    {children ?? (
      <SwitchPrimitive.Thumb className="bg-paper size-5 rounded-full shadow-sm transition-transform duration-150 ease-out data-checked:translate-x-4" />
    )}
  </SwitchPrimitive.Root>
)

export { Switch }
