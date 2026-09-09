import { screen } from "@testing-library/react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { SettingsConsole } from "./settings-console"

describe("settings console", () => {
  test("gives specialists a clear profile and workspace settings view", () => {
    renderWithProviders(
      <SettingsConsole displayName="Alex Morgan" email="alex@example.local" isAdmin={true} />,
    )

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument()
    expect(screen.queryByText("Workspace preferences")).not.toBeInTheDocument()
    expect(screen.queryByRole("switch", { name: "Desktop notifications" })).not.toBeInTheDocument()
    expect(screen.getByDisplayValue("Alex Morgan")).toBeInTheDocument()
    expect(screen.getByDisplayValue("alex@example.local")).toBeInTheDocument()
  })
})
