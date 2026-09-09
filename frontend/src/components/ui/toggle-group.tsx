"use client"

import { cn } from "cn"
import { useCallback } from "react"

type ToggleGroupProps = {
  value: string
  onValueChange: (value: string) => void
  options: { value: string; label: string }[]
  className?: string
  "aria-label"?: string
}

const ToggleGroup = ({
  value,
  onValueChange,
  options,
  className,
  "aria-label": ariaLabel,
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

  return (
    <fieldset aria-label={ariaLabel} className={cn("flex flex-wrap gap-2 border-0 p-0", className)}>
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            data-value={option.value}
            aria-pressed={selected}
            onClick={handleClick}
            className={cn(
              "focus-visible:ring-steel rounded-[8px] border px-3 py-1.5 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none",
              selected
                ? "border-navy bg-navy text-paper"
                : "border-line bg-paper text-ink hover:bg-ice-2",
            )}
          >
            {option.label}
          </button>
        )
      })}
    </fieldset>
  )
}

export { ToggleGroup }
