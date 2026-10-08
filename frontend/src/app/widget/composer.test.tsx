import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { Composer } from "./composer"

describe("visitor composer", () => {
  test("keeps Send unavailable until the visitor enters a message", async () => {
    const user = userEvent.setup()
    renderWithProviders(<Composer disabled={false} sending={false} onSend={vi.fn()} />)

    const send = screen.getByRole("button", { name: "Send" })
    expect(send).toBeDisabled()

    await user.type(screen.getByLabelText("Message"), "   ")
    expect(send).toBeDisabled()

    await user.type(screen.getByLabelText("Message"), "How fast are results?")
    expect(send).toBeEnabled()
  })

  test("sends the visitor's trimmed message once", async () => {
    const user = userEvent.setup()
    const sendMessage = vi.fn(() => true)
    renderWithProviders(<Composer disabled={false} sending={false} onSend={sendMessage} />)

    await user.type(screen.getByLabelText("Message"), "  How fast are results?  ")
    await user.click(screen.getByRole("button", { name: "Send" }))

    expect(sendMessage).toHaveBeenCalledTimes(1)
    expect(sendMessage).toHaveBeenCalledWith("How fast are results?")
  })

  test("keeps the draft until the server acknowledges the send", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn(() => true)
    const { rerender } = renderWithProviders(
      <Composer disabled={false} sending={false} onSend={onSend} />,
    )
    await user.type(screen.getByLabelText("Message"), "Hello")
    await user.click(screen.getByRole("button", { name: "Send" }))
    rerender(<Composer disabled={false} sending onSend={onSend} />)
    expect(screen.getByLabelText("Message")).toHaveValue("Hello")
    rerender(<Composer disabled={false} sending={false} onSend={onSend} />)
    expect(screen.getByLabelText("Message")).toHaveValue("")
  })

  test("keeps the draft and shows a notice when the send fails", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn(() => true)
    const { rerender } = renderWithProviders(
      <Composer disabled={false} sending={false} onSend={onSend} />,
    )
    await user.type(screen.getByLabelText("Message"), "Hello")
    await user.click(screen.getByRole("button", { name: "Send" }))
    rerender(<Composer disabled={false} sending onSend={onSend} />)
    rerender(
      <Composer disabled={false} sending={false} sendError="assistant_busy" onSend={onSend} />,
    )
    expect(screen.getByLabelText("Message")).toHaveValue("Hello")
    expect(screen.getByRole("status")).toHaveTextContent(
      "Still answering your last message. Send again when it finishes.",
    )
  })

  test("shows rate limit and generic notices", () => {
    const { rerender } = renderWithProviders(
      <Composer disabled={false} sending={false} sendError="rate_limited" onSend={vi.fn()} />,
    )
    expect(screen.getByRole("status")).toHaveTextContent(
      "You're sending messages quickly. Wait a moment and try again.",
    )
    rerender(<Composer disabled={false} sending={false} sendError="invalid" onSend={vi.fn()} />)
    expect(screen.getByRole("status")).toHaveTextContent("Your message was not sent. Try again.")
  })

  test("lets the visitor draft while the bot answers but blocks sending", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn(() => true)
    renderWithProviders(<Composer disabled={false} sending={false} replying onSend={onSend} />)
    await user.type(screen.getByLabelText("Message"), "Another question")
    const send = screen.getByRole("button", { name: "Send" })
    expect(send).toBeDisabled()
    expect(send).toHaveAccessibleDescription("Wait for the reply to finish")
    await user.type(screen.getByLabelText("Message"), "{Enter}")
    expect(onSend).not.toHaveBeenCalled()
  })
})
