"use client"

import { cn } from "cn"
import * as React from "react"

import { Label } from "@/components/ui/label"

const Field = ({ className, ...props }: React.ComponentProps<"div">) => {
  return (
    <div
      data-slot="field"
      className={cn("group/field flex flex-col gap-1.5", className)}
      {...props}
    />
  )
}

const FieldLabel = ({ className, ...props }: React.ComponentProps<typeof Label>) => {
  return (
    <Label
      data-slot="field-label"
      className={cn("text-mute text-[10px] font-semibold tracking-[0.12em] uppercase", className)}
      {...props}
    />
  )
}

const FieldDescription = ({ className, ...props }: React.ComponentProps<"p">) => {
  return (
    <p
      data-slot="field-description"
      className={cn("text-mute text-xs leading-5", className)}
      {...props}
    />
  )
}

const FieldError = ({
  className,
  children,
  id,
  ...props
}: React.ComponentProps<"p"> & { children?: React.ReactNode }) => {
  const hasMessage = typeof children === "string" ? children.length > 0 : Boolean(children)
  return (
    <p id={id} data-slot="field-error" className={cn("h-4 overflow-hidden", className)} {...props}>
      <span
        role={hasMessage ? "alert" : undefined}
        className={cn(
          "text-ember block text-xs leading-4 font-normal transition-[opacity,transform] duration-200 ease-out",
          hasMessage ? "translate-y-0 opacity-100" : "translate-y-1 opacity-0",
        )}
      >
        {hasMessage ? children : "\u00a0"}
      </span>
    </p>
  )
}

export { Field, FieldLabel, FieldDescription, FieldError }
