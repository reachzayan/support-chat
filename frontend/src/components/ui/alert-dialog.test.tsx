import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useCallback, useState } from "react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from "./alert-dialog"
import { Button } from "./button"

const AlertFixture = () => {
  const [open, setOpen] = useState(false)
  const handleOpen = useCallback(() => setOpen(true), [])
  return (
    <>
      <Button type="button" onClick={handleOpen}>
        Remove response
      </Button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogTitle>Remove canned response?</AlertDialogTitle>
          <AlertDialogDescription>#hours will be permanently deleted.</AlertDialogDescription>
          <AlertDialogFooter>
            <Button type="button">Remove response</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

describe("alert dialog chrome", () => {
  test("closes when the dimmed area outside the dialog is clicked", async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertFixture />)
    await user.click(screen.getByRole("button", { name: "Remove response" }))
    expect(screen.getByText("Remove canned response?")).toBeInTheDocument()

    const overlay = document.querySelector("[data-slot='dialog-overlay']")
    if (!overlay) throw new Error("expected dialog overlay")
    await user.click(overlay)

    await waitFor(() =>
      expect(screen.queryByText("Remove canned response?")).not.toBeInTheDocument(),
    )
  })

  test("keeps footer actions on the alert frame instead of scrolling with the body", async () => {
    const user = userEvent.setup()
    renderWithProviders(<AlertFixture />)
    await user.click(screen.getByRole("button", { name: "Remove response" }))
    const dialog = await screen.findByRole("dialog")
    const remove = within(dialog).getByRole("button", { name: "Remove response" })
    const footer = remove.parentElement

    expect(dialog.className).toMatch(/\boverflow-hidden\b/)
    expect(footer?.className).toMatch(/\bshrink-0\b/)
    expect(footer?.className).toMatch(/\bsticky\b/)
    expect(footer?.className).toMatch(/\bbottom-0\b/)
  })
})
