import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useCallback, useState } from "react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { Button } from "./button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./dialog"

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

const StickyFooterFixture = () => (
  <Dialog open>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Edit canned response</DialogTitle>
        <DialogDescription>Plain-text wording is inserted into the composer.</DialogDescription>
      </DialogHeader>
      <p>Approved wording for this shortcut.</p>
      <DialogFooter>
        <Button type="button">Save response</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
)

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

  test("closes when the dimmed area outside the dialog is clicked", async () => {
    const user = userEvent.setup()
    renderWithProviders(<DialogFixture />)
    await user.click(screen.getByRole("button", { name: "Add knowledge" }))
    await screen.findByRole("dialog", { name: "Add knowledge" })

    const overlay = document.querySelector("[data-slot='dialog-overlay']")
    if (!overlay) throw new Error("expected dialog overlay")
    await user.click(overlay)

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  test("keeps footer actions on the dialog frame instead of scrolling with the body", async () => {
    renderWithProviders(<StickyFooterFixture />)
    const dialog = await screen.findByRole("dialog", { name: "Edit canned response" })
    const save = screen.getByRole("button", { name: "Save response" })
    const body = screen.getByText("Approved wording for this shortcut.")
    const bodyScroll = body.closest("[class*='overflow-y-auto']")
    const footer = save.closest("[data-slot='dialog-footer']")

    expect(dialog.className).toMatch(/\boverflow-hidden\b/)
    expect(dialog.className).not.toMatch(/\boverflow-y-auto\b/)
    expect(bodyScroll?.contains(save)).not.toBe(true)
    expect(footer?.className).toMatch(/\bshrink-0\b/)
    expect(footer?.className).toMatch(/\bsticky\b/)
    expect(footer?.className).toMatch(/\bbottom-0\b/)
  })
})
