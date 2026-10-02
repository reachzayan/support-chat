import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { AnswerDialog } from "./suggested-faq-answer-dialog"
import type { GapRecord } from "./suggested-faq-model"

const gap: GapRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  site_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  question: "How do I enroll a driver?",
  conversations: 7,
  last_seen_at: "2026-09-30T15:00:00Z",
  examples: [],
  spiking: false,
  note: null,
  status: "open",
  resolved_at: null,
}
const LONG_ANSWER = "Open the Drivers tab and choose Add driver. ".repeat(15)
const NO_REPLIES: string[] = []

const renderDialog = (isAdmin: boolean, onSubmit = vi.fn()) => {
  renderWithProviders(
    <AnswerDialog
      gap={gap}
      isAdmin={isAdmin}
      replies={NO_REPLIES}
      similar={null}
      submitting={false}
      error=""
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />,
  )
  return { onSubmit, user: userEvent.setup() }
}

describe("answer dialog", () => {
  test("recommends knowledge text for a long answer but never switches the form on its own", async () => {
    const { user } = renderDialog(true)
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })

    await user.type(within(dialog).getByLabelText("Answer"), "Use the portal.")
    expect(within(dialog).getByRole("radio", { name: /Quick reply.*Recommended/ })).toBeChecked()
    expect(within(dialog).queryByRole("radio", { name: /Knowledge text.*Recommended/ })).toBeNull()

    await user.clear(within(dialog).getByLabelText("Answer"))
    await user.click(within(dialog).getByLabelText("Answer"))
    await user.paste(LONG_ANSWER)
    expect(within(dialog).getByRole("radio", { name: /Knowledge text.*Recommended/ })).toBeVisible()
    expect(within(dialog).queryByRole("radio", { name: /Quick reply.*Recommended/ })).toBeNull()
    expect(within(dialog).getByRole("radio", { name: /Quick reply/ })).toBeChecked()
    expect(within(dialog).getByLabelText("Shortcut")).toHaveValue("enroll_driver")
  })

  test("only an admin can save to the knowledge base", async () => {
    renderDialog(false)
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })

    expect(within(dialog).getByRole("radio", { name: /Knowledge text/ })).toBeDisabled()
    expect(within(dialog).getByText("Only admins can add knowledge text.")).toBeInTheDocument()
  })

  test("sends a knowledge answer with the question as its title", async () => {
    const { user, onSubmit } = renderDialog(true)
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })

    await user.click(within(dialog).getByRole("radio", { name: /Knowledge text/ }))
    expect(within(dialog).getByLabelText("Title")).toHaveValue("How do I enroll a driver?")
    await user.click(within(dialog).getByLabelText("Answer"))
    await user.paste("Open the Drivers tab.")
    await user.click(within(dialog).getByRole("button", { name: "Save answer" }))

    expect(onSubmit).toHaveBeenCalledWith({
      kind: "knowledge",
      title: "How do I enroll a driver?",
      body: "Open the Drivers tab.",
    })
  })

  test("will not send an empty answer", async () => {
    const { user, onSubmit } = renderDialog(false)
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })

    expect(within(dialog).getByRole("button", { name: "Save answer" })).toBeDisabled()
    await user.type(within(dialog).getByLabelText("Answer"), "   ")
    expect(within(dialog).getByRole("button", { name: "Save answer" })).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
