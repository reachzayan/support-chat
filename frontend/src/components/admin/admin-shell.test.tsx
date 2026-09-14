import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import type { StaffUser } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { AdminShell } from "./admin-shell"

const { USER } = vi.hoisted(() => ({
  USER: {
    id: "11111111-1111-4111-8111-000000000001",
    email: "agent@example.local",
    display_name: "Alex Morgan",
    is_admin: true,
  } satisfies StaffUser,
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/inbox",
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock("@/lib/auth-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")
  return { ...actual, refreshSession: vi.fn().mockResolvedValue(USER) }
})

describe("admin shell", () => {
  beforeEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    })
  })

  test("keeps canonical admin navigation in a persistent shell", async () => {
    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
    )

    await waitFor(() => expect(screen.getByText("Inbox view")).toBeInTheDocument())
    expect(screen.getByRole("link", { name: "Inbox" })).toHaveAttribute("href", "/admin/inbox")
    expect(screen.getByRole("link", { name: "Knowledge base" })).toHaveAttribute(
      "href",
      "/admin/knowledge",
    )
    expect(screen.getByRole("link", { name: "Sites" })).toHaveAttribute("href", "/admin/sites")
    expect(screen.getByRole("link", { name: "Logs" })).toHaveAttribute("href", "/admin/logs")
    const accountLink = screen.getByRole("link", { name: "Alex Morgan account" })
    expect(accountLink).toHaveAttribute("href", "/admin/settings")
    expect(accountLink.closest('[data-slot="sidebar-footer"]')).not.toBeNull()
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument()
    const sidebar = screen.getByTestId("admin-sidebar")
    expect(sidebar).toHaveAttribute("data-slot", "sidebar-container")
    expect(sidebar.parentElement).toHaveAttribute("data-state", "expanded")

    const trigger = screen
      .getAllByRole("button", { name: "Toggle Sidebar" })
      .find((button) => button.getAttribute("data-sidebar") === "trigger")
    expect(trigger).toBeDefined()
    await userEvent.setup().click(trigger!)

    expect(sidebar.parentElement).toHaveAttribute("data-state", "collapsed")
  })
})
