import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import Link from "next/link"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "./drawer"

const DrawerFixture = ({ direction = "left" }: { direction?: "left" | "right" }) => (
  <>
    <button type="button">Outside action</button>
    <Drawer swipeDirection={direction}>
      <DrawerTrigger>Open navigation</DrawerTrigger>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>Workspace navigation</DrawerTitle>
          <DrawerDescription>Choose a page in your workspace.</DrawerDescription>
        </DrawerHeader>
        <Link href="/admin/inbox">Inbox</Link>
      </DrawerContent>
    </Drawer>
  </>
)

describe("drawer navigation", () => {
  test("opens a named panel and returns focus to its trigger after closing", async () => {
    const user = userEvent.setup()
    renderWithProviders(<DrawerFixture />)
    const trigger = screen.getByRole("button", { name: "Open navigation" })
    await user.click(trigger)

    const panel = await screen.findByRole("dialog", { name: "Workspace navigation" })
    expect(panel).toHaveAccessibleDescription("Choose a page in your workspace.")
    expect(screen.queryByRole("button", { name: "Outside action" })).not.toBeInTheDocument()
    await waitFor(() => expect(panel.contains(document.activeElement)).toBe(true))
    await user.click(screen.getByRole("button", { name: "Close panel" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  test("dismisses a right-hand panel with Escape", async () => {
    const user = userEvent.setup()
    renderWithProviders(<DrawerFixture direction="right" />)
    const trigger = screen.getByRole("button", { name: "Open navigation" })
    await user.click(trigger)
    await screen.findByRole("dialog", { name: "Workspace navigation" })
    await user.keyboard("{Escape}")

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  test("dismisses when tapping outside the panel", async () => {
    const user = userEvent.setup()
    renderWithProviders(<DrawerFixture />)
    await user.click(screen.getByRole("button", { name: "Open navigation" }))
    await screen.findByRole("dialog", { name: "Workspace navigation" })
    const overlay = document.querySelector("[data-slot='drawer-overlay']")
    if (!overlay) throw new Error("expected drawer backdrop")
    await user.click(overlay)

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })
})
