import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { getAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import LoginPage from "./page"

const push = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}))

describe("staff login", () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.unstubAllGlobals()
    push.mockReset()
  })

  test("exposes Email, Password, and Sign in", () => {
    renderWithProviders(<LoginPage />)

    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByLabelText("Password")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument()
  })

  test("shows inline validation before attempting sign in", async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />)

    await user.click(screen.getByRole("button", { name: "Sign in" }))

    expect(screen.getByText("Email is required.")).toBeInTheDocument()
    expect(screen.getByText("Password is required.")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true")
    expect(screen.getByLabelText("Password")).toHaveAttribute("aria-invalid", "true")
  })

  test("never writes the access JWT to localStorage", async () => {
    const user = userEvent.setup()
    const setItem = vi.spyOn(Storage.prototype, "setItem")
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          access_token: "jwt-access-token-literal",
          user: {
            id: "11111111-1111-4111-8111-000000000001",
            email: "agent@example.local",
            display_name: "Alex Morgan",
            is_admin: false,
          },
        }),
      }),
    )

    renderWithProviders(<LoginPage />)
    await user.type(screen.getByLabelText("Email"), "agent@example.local")
    await user.type(screen.getByLabelText("Password"), "secret")
    await user.click(screen.getByRole("button", { name: "Sign in" }))

    await waitFor(() => {
      expect(getAccessToken()).toBe("jwt-access-token-literal")
    })
    expect(window.localStorage.getItem("access_token")).toBeNull()
    expect(window.localStorage.getItem("accessToken")).toBeNull()
    expect(window.localStorage.getItem("supportchat_access")).toBeNull()
    expect(JSON.stringify(window.localStorage)).not.toContain("jwt-access-token-literal")
    expect(setItem.mock.calls.flat().join(" ")).not.toContain("jwt-access-token-literal")
    expect(push).toHaveBeenCalledWith("/admin/inbox")
  })
})
