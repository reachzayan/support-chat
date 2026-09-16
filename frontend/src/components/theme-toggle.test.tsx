import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { ThemeToggle } from "./theme-toggle"

const themeCookie = () => {
  const match = document.cookie.match(/(?:^|; )supportchat_theme=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

describe("theme toggle", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark", "theme-transition")
    document.cookie = "supportchat_theme=; path=/; max-age=0"
    window.localStorage.clear()
  })

  test("switches the document theme and remembers the choice in context", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />)

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeInTheDocument(),
    )
    await user.click(screen.getByRole("button", { name: "Switch to dark mode" }))

    expect(document.documentElement).toHaveClass("dark")
    expect(document.documentElement).toHaveClass("theme-transition")
    expect(themeCookie()).toBe("dark")
    expect(window.localStorage.getItem("supportchat.theme")).toBeNull()
    expect(window.sessionStorage.getItem("supportchat.theme")).toBeNull()
    expect(screen.getByRole("button", { name: "Switch to light mode" })).toBeInTheDocument()
  })

  test("starts dark when preferences seed dark theme", () => {
    renderWithProviders(<ThemeToggle />, { initialTheme: "dark" })
    expect(screen.getByRole("button", { name: "Switch to light mode" })).toBeInTheDocument()
  })
})
