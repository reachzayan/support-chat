"use client"

import type { ReactNode } from "react"

import { PreferencesProvider, type Theme } from "@/components/preferences-context"
import { Toaster } from "@/components/ui/toast"

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
    <Toaster>{children}</Toaster>
  </PreferencesProvider>
)
