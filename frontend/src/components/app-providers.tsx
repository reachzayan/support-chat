"use client"

import type { ReactNode } from "react"

import { PreferencesProvider, type Theme } from "@/components/preferences-context"

export const AppProviders = ({
  children,
  initialTheme,
  initialSidebarOpen,
}: {
  children: ReactNode
  initialTheme?: Theme
  initialSidebarOpen?: boolean
}) => (
  <PreferencesProvider initialTheme={initialTheme} initialSidebarOpen={initialSidebarOpen}>
    {children}
  </PreferencesProvider>
)
