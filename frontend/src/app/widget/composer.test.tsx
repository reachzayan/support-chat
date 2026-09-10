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
    const sendMessage = vi.fn()
    renderWithProviders(<Composer disabled={false} sending={false} onSend={sendMessage} />)

    await user.type(screen.getByLabelText("Message"), "  How fast are results?  ")
    await user.click(screen.getByRole("button", { name: "Send" }))

    expect(sendMessage).toHaveBeenCalledTimes(1)
    expect(sendMessage).toHaveBeenCalledWith("How fast are results?")
    expect(screen.getByLabelText("Message")).toHaveValue("")
  })
})
