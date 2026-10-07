import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, test, vi } from "vitest"

import { NotificationsProvider } from "@/components/notifications/notifications-context"
import { renderWithProviders } from "@/test/render"

import { SettingsConsole } from "./settings-console"

const originalLocation = window.location
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))

const stubReplace = () => {
  const replace = vi.fn()
  const assign = vi.fn()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      assign,
      replace,
      href: "http://localhost:3000/admin/settings",
      origin: "http://localhost:3000",
      pathname: "/admin/settings",
      search: "",
      hash: "",
    },
  })
  return { replace, assign }
}

describe("settings console", () => {
  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    })
    vi.unstubAllGlobals()
  })

  test("gives specialists a clear profile and workspace settings view", () => {
    renderWithProviders(
      <NotificationsProvider enabled={false}>
        <SettingsConsole displayName="Alex Morgan" email="alex@example.local" isAdmin={true} />
      </NotificationsProvider>,
    )

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument()
    expect(screen.queryByText("Workspace preferences")).not.toBeInTheDocument()
    expect(screen.queryByRole("switch", { name: "Desktop notifications" })).not.toBeInTheDocument()
    expect(screen.queryByText("SampleSite operations")).not.toBeInTheDocument()
    expect(screen.queryByText("supportchat / samplesite")).not.toBeInTheDocument()
    expect(screen.getByText("Alex Morgan")).toBeInTheDocument()
    expect(screen.getByText("alex@example.local")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Notification settings" })).toHaveAttribute(
      "href",
      "/admin/notifications",
    )
    expect(screen.queryByRole("switch", { name: "Message tone" })).not.toBeInTheDocument()
    expect(screen.queryByDisplayValue("Alex Morgan")).not.toBeInTheDocument()
    expect(document.querySelector(".view-transition-enter")).toBeInTheDocument()
  })

  test("Sign out posts logout with the CSRF header and sends the specialist to login", async () => {
    document.cookie = "supportchat_csrf=csrf-settings"
    const { replace, assign } = stubReplace()
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({}),
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(
      <NotificationsProvider enabled={false}>
        <SettingsConsole displayName="Alex Morgan" email="alex@example.local" isAdmin={true} />
      </NotificationsProvider>,
    )

    await user.click(screen.getAllByRole("button", { name: "Sign out" })[0]!)

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(assign).not.toHaveBeenCalled()
    const logoutCall = vi
      .mocked(fetch)
      .mock.calls.find((call) => String(call[0]) === "/auth/logout")
    expect(logoutCall).toBeDefined()
    expect(new Headers(logoutCall?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf-settings")
  })
})
