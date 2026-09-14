import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { ThemeToggle } from "./theme-toggle"

describe("theme toggle", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark")
    window.localStorage.clear()
  })

  test("switches the document theme and remembers the choice", async () => {
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />)

    await user.click(await screen.findByRole("button", { name: "Switch to dark mode" }))

    expect(document.documentElement).toHaveClass("dark")
    expect(document.documentElement).toHaveClass("theme-transition")
    expect(window.localStorage.getItem("supportchat.theme")).toBe("dark")
    expect(screen.getByRole("button", { name: "Switch to light mode" })).toBeInTheDocument()
  })
})
