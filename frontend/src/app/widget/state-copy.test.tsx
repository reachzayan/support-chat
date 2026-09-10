import { screen } from "@testing-library/react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { ChatStatus } from "./chat-status"

describe("conversation state copy", () => {
  test("an idle conversation has no standalone status banner", () => {
    renderWithProviders(<ChatStatus reconnecting={false} />)
    expect(screen.queryByText("Waiting for a specialist")).not.toBeInTheDocument()
  })

  test("human and closed lifecycle copy stays with the transcript", () => {
    const { rerender } = renderWithProviders(<ChatStatus reconnecting={false} />)
    expect(screen.queryByText("Chatting with Alex Morgan")).not.toBeInTheDocument()

    rerender(<ChatStatus reconnecting={false} />)
    expect(screen.queryByText("This chat is closed")).not.toBeInTheDocument()
  })

  test("reconnecting keeps the transcript status", () => {
    renderWithProviders(<ChatStatus reconnecting={true} />)
    expect(screen.getByText("Reconnecting…")).toBeInTheDocument()
  })
})
