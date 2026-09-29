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
  return {
    ...actual,
    refreshSession: vi.fn().mockResolvedValue({ status: "authenticated", user: USER }),
  }
})

const sidebarCookie = () => {
  const match = document.cookie.match(/(?:^|; )sidebar_state=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

const stubMedia = () => {
  document.cookie = "sidebar_state=; path=/; max-age=0"
  document.cookie = "supportchat_theme=; path=/; max-age=0"
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  })
}

describe("admin shell", () => {
  beforeEach(stubMedia)

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
    expect(screen.getByRole("link", { name: "Blocked" })).toHaveAttribute("href", "/admin/blocked")
    expect(screen.getByRole("link", { name: "Logs" })).toHaveAttribute("href", "/admin/logs")
    const accountLink = screen.getByRole("link", { name: "Alex Morgan account" })
    expect(accountLink).toHaveAttribute("href", "/admin/settings")
    expect(accountLink.closest('[data-slot="sidebar-footer"]')).not.toBeNull()
    const footer = accountLink.closest('[data-slot="sidebar-footer"]')
    expect(footer?.querySelector('[data-sidebar="trigger"]')).not.toBeNull()
    expect(
      footer?.querySelector(
        'button[aria-label="Switch to dark mode"], button[aria-label="Switch to light mode"]',
      ),
    ).not.toBeNull()
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
    expect(sidebar.className).toMatch(/border-r-0/)
    expect(screen.getByRole("link", { name: "Alex Morgan account" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Alex Morgan account" })).toHaveTextContent("AM")
    const wrapper = sidebar.closest('[data-slot="sidebar-wrapper"]')
    expect(wrapper).toHaveStyle({ "--sidebar-width-icon": "3rem" })
    expect(sidebarCookie()).toBe("false")
    expect(window.localStorage.getItem("sidebar_state")).toBeNull()
    const signOut = screen.getByRole("button", { name: "Sign out" })
    expect(signOut).not.toHaveTextContent("Sign out")
    expect(signOut.querySelector("svg")).not.toBeNull()
  })

  test("restores a collapsed sidebar from the preferences cookie", async () => {
    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
      { initialSidebarOpen: false },
    )

    await waitFor(() => expect(screen.getByText("Inbox view")).toBeInTheDocument())
    expect(screen.getByTestId("admin-sidebar").parentElement).toHaveAttribute(
      "data-state",
      "collapsed",
    )
  })
})

describe("admin shell hover peek", () => {
  beforeEach(stubMedia)

  test("expands a collapsed sidebar while hovered, then restores it without saving", async () => {
    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
      { initialSidebarOpen: false },
    )
    await waitFor(() => expect(screen.getByText("Inbox view")).toBeInTheDocument())
    const knowledge = screen.getByRole("link", { name: "Knowledge base" })
    expect(knowledge).not.toHaveTextContent("Knowledge base")

    const user = userEvent.setup()
    const sidebar = screen.getByTestId("admin-sidebar")
    await user.hover(sidebar)
    expect(knowledge).toHaveTextContent("Knowledge base")
    expect(sidebarCookie()).toBeNull()

    await user.unhover(sidebar)
    expect(knowledge).not.toHaveTextContent("Knowledge base")
    expect(sidebarCookie()).toBeNull()
    expect(sidebar.parentElement).toHaveAttribute("data-state", "collapsed")
  })

  test("keeps a pinned-open sidebar expanded after the pointer leaves", async () => {
    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
    )
    await waitFor(() => expect(screen.getByText("Inbox view")).toBeInTheDocument())
    const knowledge = screen.getByRole("link", { name: "Knowledge base" })
    expect(knowledge).toHaveTextContent("Knowledge base")

    const user = userEvent.setup()
    const sidebar = screen.getByTestId("admin-sidebar")
    await user.hover(sidebar)
    await user.unhover(sidebar)
    expect(knowledge).toHaveTextContent("Knowledge base")
    expect(sidebar.parentElement).toHaveAttribute("data-state", "expanded")
  })
})
