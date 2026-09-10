import { screen } from "@testing-library/react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { Transcript } from "./transcript"

const VISITOR_LINE = "How fast are results?"
const VISITOR_LINES = [{ id: 1, role: "visitor", body: VISITOR_LINE }]
const MIXED_LINES = [
  { id: 1, role: "visitor", body: VISITOR_LINE },
  { id: 2, role: "system", body: "Your application is being reviewed." },
  { id: 3, role: "system", body: "A human has joined." },
]
const AGENT_REPLY_LINES = [
  { id: 7, role: "agent", body: "Drug and alcohol testing.\n\nRandom programs nationwide." },
]
const FOLLOW_UP_LINES = [...VISITOR_LINES, { id: 41, role: "agent", body: "Your result is ready." }]

describe("transcript typing indicator", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    })
  })
  test("active typing shows the assistant is typing copy", () => {
    renderWithProviders(<Transcript lines={VISITOR_LINES} typing={true} />)

    expect(screen.getByText(VISITOR_LINE)).toBeInTheDocument()
    expect(screen.getByText("Agent is typing…")).toBeInTheDocument()
  })

  test("inactive typing does not show the assistant indicator", () => {
    renderWithProviders(<Transcript lines={VISITOR_LINES} typing={false} />)

    expect(screen.getByText(VISITOR_LINE)).toBeInTheDocument()
    expect(screen.queryByText("Agent is typing…")).not.toBeInTheDocument()
  })

  test("keeps lifecycle notices centered while treating other system copy as an agent message", () => {
    renderWithProviders(<Transcript lines={MIXED_LINES} />)

    expect(screen.queryByText("You")).not.toBeInTheDocument()
    expect(screen.getByText(VISITOR_LINE).closest(".widget-bubble")).toHaveClass("ml-auto")
    expect(screen.getByText("Agent")).toBeInTheDocument()
    expect(
      screen.getByText("Your application is being reviewed.").closest(".widget-bubble"),
    ).toHaveClass("mr-auto")
    expect(screen.getByText("A human has joined.").closest(".widget-bubble")).toHaveClass("mx-auto")
  })

  test("keeps paragraph breaks in agent replies", () => {
    renderWithProviders(<Transcript lines={AGENT_REPLY_LINES} />)

    expect(screen.getByText(/Random programs nationwide/).closest(".widget-bubble")).toHaveClass(
      "whitespace-pre-wrap",
    )
  })

  test("follows a newly received message to the latest point in the transcript", () => {
    const { rerender } = renderWithProviders(<Transcript autoFollow lines={VISITOR_LINES} />)
    const scrollIntoView = HTMLElement.prototype.scrollIntoView as ReturnType<typeof vi.fn>
    scrollIntoView.mockClear()

    rerender(<Transcript autoFollow lines={FOLLOW_UP_LINES} />)

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "end" })
  })
})
