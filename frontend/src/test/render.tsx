/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

import { render, type RenderOptions } from "@testing-library/react"
import type { ReactElement } from "react"

import { PreferencesProvider, type Theme } from "@/components/preferences-context"

type ProviderOptions = {
  initialTheme?: Theme
  initialSidebarOpen?: boolean
}

export const renderWithProviders = (
  ui: ReactElement,
  options?: RenderOptions & ProviderOptions,
) => {
  const { initialTheme, initialSidebarOpen, ...renderOptions } = options ?? {}
  return render(ui, {
    ...renderOptions,
    wrapper: ({ children }) => (
      <PreferencesProvider initialTheme={initialTheme} initialSidebarOpen={initialSidebarOpen}>
        {children}
      </PreferencesProvider>
    ),
  })
}
