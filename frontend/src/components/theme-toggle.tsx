"use client"

import { Moon, Sun } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"

const THEME_KEY = "supportchat.theme"

export const ThemeToggle = ({ compact = false }: { compact?: boolean }) => {
  const [dark, setDark] = useState(false)
  const transitionTimeout = useRef<number | null>(null)

  // The browser preference is read after hydration to keep the server markup stable.
  useEffect(() => {
    const stored = window.localStorage.getItem(THEME_KEY)
    const prefersDark =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    const next = stored === "dark" || (stored === null && prefersDark)
    document.documentElement.classList.toggle("dark", next)
    // oxlint-disable-next-line react/set-state-in-effect
    setDark(next)
    return () => {
      if (transitionTimeout.current !== null) {
        window.clearTimeout(transitionTimeout.current)
      }
      document.documentElement.classList.remove("theme-transition")
    }
  }, [])

  const handleToggle = useCallback(() => {
    const next = !dark
    document.documentElement.classList.add("theme-transition")
    document.documentElement.classList.toggle("dark", next)
    window.localStorage.setItem(THEME_KEY, next ? "dark" : "light")
    setDark(next)
    if (transitionTimeout.current !== null) {
      window.clearTimeout(transitionTimeout.current)
    }
    transitionTimeout.current = window.setTimeout(() => {
      document.documentElement.classList.remove("theme-transition")
      transitionTimeout.current = null
    }, 220)
  }, [dark, transitionTimeout])

  return (
    <Button
      type="button"
      variant="ghost"
      size={compact ? "icon-sm" : "icon"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={handleToggle}
      className={compact ? "text-white/85 hover:bg-white/10 hover:text-white" : "text-mute"}
    >
      {dark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  )
}
