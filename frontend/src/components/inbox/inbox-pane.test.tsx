import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { InboxConsole } from "./inbox-console"
import { ALEX, resetInboxHarness } from "./inbox-test-harness"

const WIDTH_KEY = "supportchat.inbox.list-width"

const listPane = () => screen.getByRole("heading", { name: "Conversations" }).closest("section")

describe("inbox list pane width", () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetInboxHarness()
  })

  test("opens the conversation list at 360 px when nothing is stored", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(listPane()).toHaveStyle({ width: "360px" }))
  })

  test("restores a stored conversation list width of 400 px", async () => {
    window.localStorage.setItem(WIDTH_KEY, "400")
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(listPane()).toHaveStyle({ width: "400px" }))
  })

  test("a stored width of 50 px opens at 280 px", async () => {
    window.localStorage.setItem(WIDTH_KEY, "50")
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(listPane()).toHaveStyle({ width: "280px" }))
  })

  test("a stored width of 900 px opens at 640 px", async () => {
    window.localStorage.setItem(WIDTH_KEY, "900")
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(listPane()).toHaveStyle({ width: "640px" }))
  })

  test("arrow right from the default width persists 384 px", async () => {
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    const handle = await screen.findByRole("button", { name: "Resize conversation list" })
    handle.focus()
    await user.keyboard("{ArrowRight}")
    await waitFor(() => expect(listPane()).toHaveStyle({ width: "384px" }))
    expect(window.localStorage.getItem(WIDTH_KEY)).toBe("384")
  })

  test("double-click on the resize handle restores 360 px", async () => {
    window.localStorage.setItem(WIDTH_KEY, "400")
    renderWithProviders(<InboxConsole user={ALEX} />)
    const handle = await screen.findByRole("button", { name: "Resize conversation list" })
    fireEvent.doubleClick(handle)
    await waitFor(() => expect(listPane()).toHaveStyle({ width: "360px" }))
    expect(window.localStorage.getItem(WIDTH_KEY)).toBe("360")
  })

  test("resize handle does not draw a second divider next to the pane border", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    const handle = await screen.findByRole("button", { name: "Resize conversation list" })
    expect(handle.querySelector("span")).toBeNull()
    expect(handle.className).not.toMatch(/hover:bg-steel/)
    expect(listPane()?.className).toMatch(/border-r/)
    expect(listPane()?.className).toMatch(/pane-resize:hover/)
  })
})
