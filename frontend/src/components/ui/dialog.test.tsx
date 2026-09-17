import { screen } from "@testing-library/react"
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
  test("opens with a sharp, unblurred frame and no trigger-origin morph", async () => {
    const user = userEvent.setup()
    renderWithProviders(<DialogFixture />)
    await user.click(screen.getByRole("button", { name: "Add knowledge" }))

    const dialog = screen.getByRole("dialog")
    expect(dialog).not.toHaveAttribute("data-origin-left")
    expect(dialog).not.toHaveAttribute("data-origin-top")
    expect(dialog.className).not.toMatch(/-translate-x-1\/2/)
    expect(dialog.className).not.toMatch(/backdrop-blur/)
    expect(dialog.className).toMatch(/border-line/)
    expect(dialog.className).toMatch(/bg-paper/)

    const overlay = document.querySelector('[data-slot="dialog-overlay"]')
    expect(overlay).not.toBeNull()
    expect(overlay?.className).not.toMatch(/backdrop-blur/)
  })
})
