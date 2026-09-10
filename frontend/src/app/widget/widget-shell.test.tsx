import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { WidgetShell } from "./widget-shell"

describe("widget shell", () => {
  test("opens with the widget entrance motion", () => {
    renderWithProviders(
      <WidgetShell name="SupportChat" onClose={vi.fn()} onReset={vi.fn()}>
        <p>Conversation content</p>
      </WidgetShell>,
    )

    expect(screen.getByRole("dialog")).toHaveClass("widget-enter")
  })

  test("presents a minimal support panel with direct reset and clear disclaimers", async () => {
    const user = userEvent.setup()
    const onReset = vi.fn()
    renderWithProviders(
      <WidgetShell name="Text AI Support" onClose={vi.fn()} onReset={onReset}>
        <p>Conversation content</p>
      </WidgetShell>,
    )

    expect(screen.getByRole("heading", { name: "Text AI Support" })).toBeInTheDocument()
    expect(screen.getByText("Secure, assisted support")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reset chat" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Close chat" })).toBeInTheDocument()
    expect(screen.queryByText("Support", { exact: true })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "More options" })).not.toBeInTheDocument()
    expect(
      screen.getByText("AI responses may be incorrect. Do not share sensitive information."),
    ).toBeInTheDocument()
    expect(screen.getByRole("main")).toHaveTextContent("Conversation content")

    await user.click(screen.getByRole("button", { name: "Reset chat" }))

    expect(onReset).toHaveBeenCalledOnce()
  })
})
