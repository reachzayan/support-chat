"use client"

import type { ReactNode } from "react"

import { PreferencesProvider, type Theme } from "@/components/preferences-context"
import { Toaster } from "@/components/ui/toast"

export const AppProviders = ({
  children,
  initialTheme,
  initialSidebarOpen,
  initialNotificationSound,
}: {
  children: ReactNode
  initialTheme?: Theme
  initialSidebarOpen?: boolean
  initialNotificationSound?: boolean
}) => (
  <PreferencesProvider
    initialTheme={initialTheme}
    initialSidebarOpen={initialSidebarOpen}
    initialNotificationSound={initialNotificationSound}
  >
    <Toaster>{children}</Toaster>
  </PreferencesProvider>
)
