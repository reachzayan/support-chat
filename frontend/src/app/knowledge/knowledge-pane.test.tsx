import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import { knowledgeFetch } from "./knowledge-test-fetch"

const WIDTH_KEY = "supportchat.knowledge.source-width"

const sourcePane = () => screen.getByRole("heading", { name: "Sources" }).closest("section")

describe("knowledge source pane width", () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("opens the source list at 448 px when nothing is stored", async () => {
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(sourcePane()).toHaveStyle({ width: "448px" }))
  })

  test("restores a stored source list width of 360 px", async () => {
    window.localStorage.setItem(WIDTH_KEY, "360")
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(sourcePane()).toHaveStyle({ width: "360px" }))
  })

  test("arrow right from the default width persists 472 px", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    const handle = await screen.findByRole("button", { name: "Resize source list" })
    handle.focus()
    await user.keyboard("{ArrowRight}")
    await waitFor(() => expect(sourcePane()).toHaveStyle({ width: "472px" }))
    expect(window.localStorage.getItem(WIDTH_KEY)).toBe("472")
  })

  test("double-click on the resize handle restores 448 px", async () => {
    window.localStorage.setItem(WIDTH_KEY, "360")
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    const handle = await screen.findByRole("button", { name: "Resize source list" })
    await waitFor(() => expect(sourcePane()).toHaveStyle({ width: "360px" }))
    fireEvent.doubleClick(handle)
    await waitFor(() => expect(sourcePane()).toHaveStyle({ width: "448px" }))
    expect(window.localStorage.getItem(WIDTH_KEY)).toBe("448")
  })
})
