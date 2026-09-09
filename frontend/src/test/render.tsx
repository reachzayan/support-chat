import { render, type RenderOptions } from "@testing-library/react"
import type { ReactElement } from "react"

export const renderWithProviders = (ui: ReactElement, options?: RenderOptions) => {
  return render(ui, options)
}
