import { screen } from "@testing-library/react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { StaffNav } from "./staff-nav"

describe("staff navigation", () => {
  test("provides a persistent workspace rail for the core staff views", () => {
    renderWithProviders(<StaffNav current="Inbox" displayName="Alex Morgan" />)

    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Inbox" })).toHaveAttribute("href", "/admin/inbox")
    expect(screen.getByRole("link", { name: "Knowledge base" })).toHaveAttribute(
      "href",
      "/admin/knowledge",
    )
    expect(screen.getByRole("link", { name: "Sites" })).toHaveAttribute("href", "/admin/sites")
    expect(screen.getByRole("link", { name: "Logs" })).toHaveAttribute("href", "/admin/logs")
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/admin/settings",
    )
    expect(screen.getByText("Operations workspace")).toBeInTheDocument()
    expect(screen.getByText("Alex Morgan")).toBeInTheDocument()
  })
})
