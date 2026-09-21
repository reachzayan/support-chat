import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { WidgetShell } from "./widget-shell"

describe("widget shell", () => {
  test("opens with the widget entrance motion", () => {
    renderWithProviders(
      <WidgetShell name="SupportChat" onClose={vi.fn()} onResetCurrent={vi.fn()} onDeleteAll={vi.fn()}>
        <p>Conversation content</p>
      </WidgetShell>,
    )

    expect(screen.getByRole("dialog")).toHaveClass("widget-enter")
  })

  test("puts reset and browser-history removal in an accessible overflow menu", async () => {
    const user = userEvent.setup()
    const onResetCurrent = vi.fn()
    const onDeleteAll = vi.fn()
    renderWithProviders(
      <WidgetShell
        name="Text AI Support"
        onClose={vi.fn()}
        onResetCurrent={onResetCurrent}
        onDeleteAll={onDeleteAll}
      >
        <p>Conversation content</p>
      </WidgetShell>,
    )

    expect(screen.getByRole("heading", { name: "Text AI Support" })).toBeInTheDocument()
    expect(screen.getByText("Secure, assisted support")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Reset chat" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Close chat" })).toBeInTheDocument()
    expect(screen.queryByText("Support", { exact: true })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "More options" })).toBeInTheDocument()
    expect(
      screen.getByText("AI responses may be incorrect. Do not share sensitive information."),
    ).toBeInTheDocument()
    expect(screen.getByRole("main")).toHaveTextContent("Conversation content")

    await user.click(screen.getByRole("button", { name: "More options" }))
    await user.click(screen.getByRole("menuitem", { name: "Reset current chat" }))
    expect(screen.getByRole("alertdialog", { name: "Reset current chat?" })).toBeInTheDocument()
    expect(screen.getByText(/saved in your chat history/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(onResetCurrent).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "More options" }))
    await user.click(screen.getByRole("menuitem", { name: "Delete all chats" }))
    expect(
      screen.getByRole("alertdialog", { name: "Delete all chats from this browser?" }),
    ).toBeInTheDocument()
    expect(screen.getByText(/retained support records/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Delete all chats" }))
    expect(onDeleteAll).toHaveBeenCalledOnce()
  })
})
