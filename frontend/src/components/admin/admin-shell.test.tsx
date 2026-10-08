import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { refreshSession, type StaffUser } from "@/lib/auth-client"
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
  vi.mocked(refreshSession).mockResolvedValue({ status: "authenticated", user: USER })
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  })
}

test("selected page and navigation toggle retain their state after the pointer leaves", async () => {
  stubMedia()
  const user = userEvent.setup()
  renderWithProviders(
    <AdminShell>
      <div>Inbox view</div>
    </AdminShell>,
  )
  await screen.findByText("Inbox view")
  const inbox = screen.getByRole("link", { name: "Inbox" })
  const sites = screen.getByRole("link", { name: "Sites" })
  const toggle = screen.getByRole("button", { name: "Toggle Sidebar" })
  expect(inbox).toHaveAttribute("aria-current", "page")
  expect(sites).not.toHaveAttribute("aria-current")
  expect(toggle).toHaveAttribute("aria-expanded", "true")
  await user.click(toggle)
  await user.unhover(toggle)
  expect(toggle).toHaveAttribute("aria-expanded", "false")
  expect(inbox).toHaveAttribute("aria-current", "page")
  await user.click(toggle)
  await user.unhover(toggle)
  expect(toggle).toHaveAttribute("aria-expanded", "true")
})

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
    expect(screen.getByRole("link", { name: "Status" })).toHaveAttribute("href", "/admin/status")
    expect(screen.getByRole("link", { name: "Knowledge base" })).toHaveAttribute(
      "href",
      "/admin/knowledge",
    )
    expect(screen.getByRole("link", { name: "Sites" })).toHaveAttribute("href", "/admin/sites")
    expect(screen.getByRole("link", { name: "Blocked" })).toHaveAttribute("href", "/admin/blocked")
    expect(screen.getByRole("link", { name: "Logs" })).toHaveAttribute("href", "/admin/logs")
    expect(screen.queryByText("Accepting chats")).not.toBeInTheDocument()
    expect(screen.getByText("Admin")).toBeInTheDocument()
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

  test("places Status immediately above Logs in the workspace nav", async () => {
    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
    )

    await waitFor(() => expect(screen.getByText("Inbox view")).toBeInTheDocument())
    const labels = within(screen.getByTestId("admin-sidebar"))
      .getAllByRole("link")
      .map((link) => link.textContent)
    expect(labels.indexOf("Status")).toBe(labels.indexOf("Logs") - 1)
    expect(labels.indexOf("Sites")).toBeLessThan(labels.indexOf("Status"))
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
    expect(screen.getByRole("link", { name: "Notification settings" })).toHaveAttribute(
      "href",
      "/admin/notifications",
    )
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

const stubLocation = () => {
  const replace = vi.fn()
  const assign = vi.fn()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      replace,
      assign,
      href: "http://localhost:3000/admin/inbox",
      origin: "http://localhost:3000",
      pathname: "/admin/inbox",
      search: "",
      hash: "",
    },
  })
  return { replace, assign }
}

describe("admin shell session gate", () => {
  const originalLocation = window.location

  beforeEach(stubMedia)

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    })
  })

  test("sends a signed-out specialist to Sign in and never shows the staff API outage", async () => {
    const { replace, assign } = stubLocation()
    vi.mocked(refreshSession).mockResolvedValue({ status: "unauthenticated" })

    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
    )

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(assign).not.toHaveBeenCalled()
    expect(screen.queryByText("Could not reach the staff API.")).not.toBeInTheDocument()
    expect(screen.queryByText("Inbox view")).not.toBeInTheDocument()
  })

  test("keeps the staff API outage when a signed-in session cannot reach refresh", async () => {
    const { replace } = stubLocation()
    vi.mocked(refreshSession).mockResolvedValue({ status: "unavailable" })

    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
    )

    await waitFor(() =>
      expect(screen.getByText("Could not reach the staff API.")).toBeInTheDocument(),
    )
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument()
    expect(replace).not.toHaveBeenCalled()
    expect(screen.queryByText("Inbox view")).not.toBeInTheDocument()
  })

  test("re-checks the session when the browser restores the admin page from history", async () => {
    const { replace } = stubLocation()
    vi.mocked(refreshSession)
      .mockResolvedValueOnce({ status: "authenticated", user: USER })
      .mockResolvedValueOnce({ status: "unauthenticated" })

    renderWithProviders(
      <AdminShell>
        <div id="main-content">Inbox view</div>
      </AdminShell>,
    )
    await waitFor(() => expect(screen.getByText("Inbox view")).toBeInTheDocument())

    const pageshow = new Event("pageshow")
    Object.defineProperty(pageshow, "persisted", { value: true })
    window.dispatchEvent(pageshow)

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(screen.queryByText("Could not reach the staff API.")).not.toBeInTheDocument()
  })
})

describe("mobile admin navigation", () => {
  beforeEach(stubMedia)
  test("theme controls work from the mobile navigation footer", async () => {
    const originalWidth = window.innerWidth
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 })
    try {
      const user = userEvent.setup()
      renderWithProviders(
        <AdminShell>
          <div>Inbox view</div>
        </AdminShell>,
        { initialTheme: "light" },
      )
      await screen.findByText("Inbox view")
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
      expect(screen.queryByRole("button", { name: "Switch to dark mode" })).not.toBeInTheDocument()
      await user.click(screen.getByRole("button", { name: "Open navigation" }))
      const drawer = await screen.findByRole("dialog")
      await user.click(within(drawer).getByRole("button", { name: "Switch to dark mode" }))
      expect(document.documentElement).toHaveClass("dark")
      expect(document.cookie).toContain("supportchat_theme=dark")
      expect(
        within(drawer).getByRole("button", { name: "Switch to light mode" }),
      ).toBeInTheDocument()
      await user.click(within(drawer).getByRole("button", { name: "Close panel" }))
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    } finally {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: originalWidth })
    }
  })
  test("the navigation toggle names its state and the drawer labels the theme switch", async () => {
    const originalWidth = window.innerWidth
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 })
    try {
      const user = userEvent.setup()
      renderWithProviders(
        <AdminShell>
          <div>Inbox view</div>
        </AdminShell>,
      )
      await screen.findByText("Inbox view")
      const toggle = screen.getByRole("button", { name: "Open navigation" })
      expect(toggle).toHaveAttribute("aria-expanded", "false")
      await user.click(toggle)
      const drawer = await screen.findByRole("dialog")
      const closeToggle = screen.getByRole("button", { name: "Close navigation", hidden: true })
      expect(closeToggle).toHaveAttribute("aria-expanded", "true")
      const theme = within(drawer).getByRole("button", { name: "Switch to dark mode" })
      expect(theme).toHaveTextContent("Switch to dark mode")
    } finally {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: originalWidth })
    }
  })
  test("mobile navigation opens outside the drawer and closes after choosing a page", async () => {
    const originalWidth = window.innerWidth
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 })
    try {
      const user = userEvent.setup()
      renderWithProviders(
        <AdminShell>
          <div>Inbox view</div>
        </AdminShell>,
      )
      await screen.findByText("Inbox view")
      await user.click(screen.getByRole("button", { name: "Open navigation" }))
      const drawer = await screen.findByRole("dialog")
      expect(within(drawer).getByRole("link", { name: "Sites" })).toHaveTextContent("Sites")
      await user.click(within(drawer).getByRole("link", { name: "Sites" }))
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
      expect(screen.getByRole("button", { name: "Open navigation" })).toBeInTheDocument()
    } finally {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: originalWidth })
    }
  })
})

test("the sidebar Inbox count shares read state with the notification bell", async () => {
  stubMedia()
  vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === "POST"
      ? new Response(null, { status: 204 })
      : Response.json({
          items: [
            {
              id: 41,
              site_id: "easy",
              site_name: "SampleSite",
              conversation_id: "chat-1",
              scenario: "needs_attention",
              created_at: "2026-10-06T12:00:00Z",
              read_at: null,
            },
          ],
          unread_count: 1,
          next_cursor: null,
        }),
  )
  try {
    const user = userEvent.setup()
    renderWithProviders(
      <AdminShell>
        <div>Inbox view</div>
      </AdminShell>,
    )
    const inbox = await screen.findByRole("link", { name: "Inbox, 1 unread" })
    expect(inbox).toHaveTextContent("1")
    await user.click(screen.getByRole("button", { name: "Notifications, 1 unread" }))
    await user.click(screen.getByRole("button", { name: "Mark all read" }))
    await waitFor(() => expect(inbox).toHaveAccessibleName("Inbox"))
    expect(inbox).toHaveTextContent("Inbox")
    expect(inbox).not.toHaveTextContent("1")
  } finally {
    vi.unstubAllGlobals()
  }
})
