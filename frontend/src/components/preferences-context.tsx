"use client"

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

const THEME_COOKIE = "supportchat_theme"
const SIDEBAR_COOKIE = "sidebar_state"
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365

export type Theme = "light" | "dark"

type PreferencesContextValue = {
  theme: Theme
  dark: boolean
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  notificationSound: boolean
  setNotificationSound: (enabled: boolean) => void
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null)

const writeCookie = (name: string, value: string) => {
  if (typeof document === "undefined") {
    return
  }
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`
}

export const PreferencesProvider = ({
  children,
  initialTheme = "light",
  initialSidebarOpen = true,
  initialNotificationSound = true,
}: {
  children: ReactNode
  initialTheme?: Theme
  initialSidebarOpen?: boolean
  initialNotificationSound?: boolean
}) => {
  const [theme, setThemeState] = useState<Theme>(initialTheme)
  const [sidebarOpen, setSidebarOpenState] = useState(initialSidebarOpen)
  const [notificationSound, setSoundState] = useState(initialNotificationSound)
  const setNotificationSound = useCallback((enabled: boolean) => {
    writeCookie("supportchat_notification_sound", String(enabled))
    setSoundState(enabled)
  }, [])

  const setTheme = useCallback((next: Theme) => {
    document.documentElement.classList.toggle("dark", next === "dark")
    writeCookie(THEME_COOKIE, next)
    setThemeState(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark")
  }, [setTheme, theme])

  const setSidebarOpen = useCallback((open: boolean) => {
    writeCookie(SIDEBAR_COOKIE, open ? "true" : "false")
    setSidebarOpenState(open)
  }, [])

  const value = useMemo(
    () => ({
      theme,
      dark: theme === "dark",
      setTheme,
      toggleTheme,
      sidebarOpen,
      setSidebarOpen,
      notificationSound,
      setNotificationSound,
    }),
    [
      setSidebarOpen,
      setTheme,
      sidebarOpen,
      theme,
      toggleTheme,
      notificationSound,
      setNotificationSound,
    ],
  )

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
}

export const usePreferences = () => {
  const context = useContext(PreferencesContext)
  if (context === null) {
    throw new Error("usePreferences must be used within a PreferencesProvider.")
  }
  return context
}
