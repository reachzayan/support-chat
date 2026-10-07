"use client"

import { cn } from "cn"
import { useCallback, useRef } from "react"

import { usePreferences } from "@/components/preferences-context"
import { Button } from "@/components/ui/button"
import { StateIcon } from "@/components/ui/state-icon"

export const ThemeToggle = ({
  compact = false,
  className,
}: {
  compact?: boolean
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

  return (
    <Button
      type="button"
      variant="ghost"
      size={compact ? "icon-sm" : "icon"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={handleToggle}
      className={cn(compact ? "text-white/85 hover:text-white" : "text-mute", className)}
    >
      {dark ? <StateIcon name="sun" /> : <StateIcon name="moon" />}
    </Button>
  )
}
