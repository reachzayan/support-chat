import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { SettingsConsole } from "./settings-console"

const originalLocation = window.location

const stubAssign = () => {
  const assign = vi.fn()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      assign,
      replace: assign,
      href: "http://localhost:3000/admin/settings",
      origin: "http://localhost:3000",
      pathname: "/admin/settings",
      search: "",
      hash: "",
    },
  })
  return assign
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
      <SettingsConsole displayName="Alex Morgan" email="alex@example.local" isAdmin={true} />,
    )

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument()
    expect(screen.queryByText("Workspace preferences")).not.toBeInTheDocument()
    expect(screen.queryByRole("switch", { name: "Desktop notifications" })).not.toBeInTheDocument()
    expect(screen.getByDisplayValue("Alex Morgan")).toBeInTheDocument()
    expect(screen.getByDisplayValue("alex@example.local")).toBeInTheDocument()
    expect(document.querySelector(".view-transition-enter")).toBeInTheDocument()
  })

  test("Sign out posts logout with the CSRF header and sends the specialist to login", async () => {
    document.cookie = "supportchat_csrf=csrf-settings"
    const assign = stubAssign()
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
      <SettingsConsole displayName="Alex Morgan" email="alex@example.local" isAdmin={true} />,
    )

    await user.click(screen.getAllByRole("button", { name: "Sign out" })[0]!)

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"))
    const logoutCall = vi
      .mocked(fetch)
      .mock.calls.find((call) => String(call[0]) === "/auth/logout")
    expect(logoutCall).toBeDefined()
    expect(new Headers(logoutCall?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf-settings")
  })
})
