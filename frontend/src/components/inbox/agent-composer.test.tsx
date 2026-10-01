import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { AgentComposer } from "./agent-composer"

const LINE_PX = 24
const NO_CANNED: [] = []

beforeEach(() => {
  Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
    configurable: true,
    get(this: HTMLTextAreaElement) {
      const lines = Math.max(1, this.value.split("\n").length)
      return lines * LINE_PX
    },
  })
})

afterEach(() => {
  // restore for other suites that touch textareas
  Reflect.deleteProperty(HTMLTextAreaElement.prototype, "scrollHeight")
})

describe("agent composer field growth", () => {
  test("grows taller when the draft gains more lines", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <AgentComposer
        disabled={false}
        canned={NO_CANNED}
        inputId="agent-message"
        onSend={vi.fn(() => true)}
      />,
    )

    const field = screen.getByLabelText("Message")
    expect(field.tagName).toBe("TEXTAREA")

    await user.type(field, "Short reply")
    const oneLineHeight = Number.parseInt(field.style.height, 10)

    await user.type(field, "{Shift>}{Enter}{/Shift}Second line{Shift>}{Enter}{/Shift}Third line")
    const threeLineHeight = Number.parseInt(field.style.height, 10)

    expect(oneLineHeight).toBe(LINE_PX)
    expect(threeLineHeight).toBe(LINE_PX * 3)
    expect(threeLineHeight).toBeGreaterThan(oneLineHeight)
  })

  test("Enter without Shift sends the draft; Shift+Enter keeps editing", async () => {
    const user = userEvent.setup()
    const onSend = vi.fn(() => true)
    renderWithProviders(
      <AgentComposer
        disabled={false}
        canned={NO_CANNED}
        inputId="agent-message-send"
        onSend={onSend}
      />,
    )

    const field = screen.getByLabelText("Message")
    await user.type(field, "Line one{Shift>}{Enter}{/Shift}Line two")
    expect(field).toHaveValue("Line one\nLine two")
    expect(onSend).not.toHaveBeenCalled()

    await user.keyboard("{Enter}")
    expect(onSend).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledWith("Line one\nLine two")
    expect(field).toHaveValue("")
  })
})
