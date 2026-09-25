"use client"

import { cn } from "cn"
import { useCallback } from "react"

import { Button } from "./button"

type ToggleGroupProps = {
  value: string
  onValueChange: (value: string) => void
  options: { value: string; label: string }[]
  className?: string
  "aria-label"?: string
  /** Segmented track (Website / Plain text style). Default is separate outline chips. */
  appearance?: "default" | "segmented"
}

const ToggleGroup = ({
  value,
  onValueChange,
  options,
  className,
  "aria-label": ariaLabel,
  appearance = "default",
}: ToggleGroupProps) => {
  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      const nextValue = event.currentTarget.dataset.value
      if (nextValue) {
        onValueChange(nextValue)
      }
    },
    [onValueChange],
  )

  if (appearance === "segmented") {
    return (
      <fieldset
        aria-label={ariaLabel}
        className={cn("bg-ice-2 flex w-fit gap-1 rounded-lg border-0 p-1", className)}
      >
        {options.map((option) => {
          const selected = option.value === value
          return (
            <Button
              key={option.value}
              type="button"
              data-value={option.value}
              aria-pressed={selected}
              onClick={handleClick}
              variant="ghost"
              size="sm"
              className={cn(
                "h-7 px-3 text-xs font-bold",
                selected ? "bg-paper text-navy shadow-sm" : "text-mute hover:text-ink",
              )}
            >
              {option.label}
            </Button>
          )
        })}
      </fieldset>
    )
  }

  return (
    <fieldset aria-label={ariaLabel} className={cn("flex flex-wrap gap-2 border-0 p-0", className)}>
      {options.map((option) => {
        const selected = option.value === value
        return (
          <Button
            key={option.value}
            type="button"
            data-value={option.value}
            aria-pressed={selected}
            onClick={handleClick}
            variant="ghost"
            size="sm"
            className={cn(
              "focus-visible:ring-steel border px-3 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none",
              selected
                ? "border-navy bg-navy text-white dark:text-navy-deep"
                : "border-line bg-paper text-ink hover:bg-ice-2",
            )}
          >
            {option.label}
          </Button>
        )
      })}
    </fieldset>
  )
}

export { ToggleGroup }
