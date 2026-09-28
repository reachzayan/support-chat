import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useCallback, useState } from "react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog"

const DialogFixture = () => {
  const [open, setOpen] = useState(false)
  const handleOpen = useCallback(() => setOpen(true), [])
  return (
    <>
      <button type="button" onClick={handleOpen}>
        Add knowledge
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>Add knowledge</DialogTitle>
          <DialogDescription>Paste source URLs for this website.</DialogDescription>
        </DialogContent>
      </Dialog>
    </>
  )
}

describe("dialog chrome", () => {
  test("opens a named dialog, traps focus, and offers Close dialog", async () => {
    const user = userEvent.setup()
    renderWithProviders(<DialogFixture />)
    const trigger = screen.getByRole("button", { name: "Add knowledge" })
    await user.click(trigger)

    const dialog = await screen.findByRole("dialog", { name: "Add knowledge" })
    expect(dialog).toHaveAccessibleDescription("Paste source URLs for this website.")
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))
    expect(screen.getByRole("button", { name: "Close dialog" })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Close dialog" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })
})
