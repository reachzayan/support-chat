"use client"

import { cn } from "cn"
import { useCallback, useRef } from "react"

import { usePreferences } from "@/components/preferences-context"
import { Button } from "@/components/ui/button"
import { StateIcon } from "@/components/ui/state-icon"

export const ThemeToggle = ({
  compact = false,
  showLabel = false,
  className,
}: {
  compact?: boolean
  /** Render a visible text label next to the icon (used in the navigation drawer). */
  showLabel?: boolean
  className?: string
}) => {
  const { dark, toggleTheme } = usePreferences()
  const transitionTimeout = useRef<number | null>(null)

  const handleToggle = useCallback(() => {
    document.documentElement.classList.add("theme-transition")
    toggleTheme()
    if (transitionTimeout.current !== null) {
      window.clearTimeout(transitionTimeout.current)
    }
    transitionTimeout.current = window.setTimeout(() => {
      document.documentElement.classList.remove("theme-transition")
      transitionTimeout.current = null
    }, 220)
  }, [toggleTheme])

  const label = dark ? "Switch to light mode" : "Switch to dark mode"
  if (showLabel) {
    return (
      <Button
        type="button"
        variant="ghost"
        onClick={handleToggle}
        className={cn(
          "min-h-11 justify-start gap-2.5 px-3 text-sm font-semibold text-white/85 hover:text-white md:min-h-8",
          className,
        )}
      >
        {dark ? (
          <StateIcon name="sun" className="size-4.5" />
        ) : (
          <StateIcon name="moon" className="size-4.5" />
        )}
        {label}
      </Button>
    )
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size={compact ? "icon-sm" : "icon"}
      aria-label={label}
      title={label}
      onClick={handleToggle}
      className={cn(compact ? "text-white/85 hover:text-white" : "text-mute", className)}
    >
      {dark ? <StateIcon name="sun" /> : <StateIcon name="moon" />}
    </Button>
  )
}
