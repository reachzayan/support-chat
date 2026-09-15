import { act, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { Transcript } from "./transcript"

const VISITOR_LINE = "How fast are results?"
const IDLE_WARNING = "This chat will be closed in one minute. Send any message to keep active."
const NOW = new Date("2026-09-15T12:00:00.000Z")
const FOUR_MIN_AGO = "2026-09-15T11:56:00.000Z"
const THREE_MIN_AGO = "2026-09-15T11:57:00.000Z"
const JUST_NOW = "2026-09-15T12:00:00.000Z"

const IDLE_LINE_THREE_MIN = [
  { id: 1, role: "visitor", body: VISITOR_LINE, created_at: THREE_MIN_AGO },
]
const IDLE_LINE_FOUR_MIN = [
  { id: 1, role: "visitor", body: VISITOR_LINE, created_at: FOUR_MIN_AGO },
]
const IDLE_LINES_AT_FOUR_MIN = [
  { id: 1, role: "visitor", body: VISITOR_LINE, created_at: FOUR_MIN_AGO },
  {
    id: 2,
    role: "bot",
    body: "Most results report within 24-48 hours.",
    created_at: FOUR_MIN_AGO,
  },
]
const IDLE_LINES_AFTER_VISITOR_REPLY = [
  ...IDLE_LINES_AT_FOUR_MIN,
  { id: 3, role: "visitor", body: "Thanks", created_at: JUST_NOW },
]

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
    expect(screen.getByText("Assistant is typing…")).toBeInTheDocument()
  })

  test("inactive typing does not show the assistant indicator", () => {
    renderWithProviders(<Transcript lines={VISITOR_LINES} typing={false} />)

    expect(screen.getByText(VISITOR_LINE)).toBeInTheDocument()
    expect(screen.queryByText("Assistant is typing…")).not.toBeInTheDocument()
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

describe("transcript idle close warning", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    })
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test("does not show the warning before four minutes of visitor idle", () => {
    renderWithProviders(<Transcript conversationState="bot" lines={IDLE_LINE_THREE_MIN} />)

    expect(screen.queryByText(IDLE_WARNING)).not.toBeInTheDocument()
  })

  test("shows the warning at four minutes of visitor idle in bot", () => {
    renderWithProviders(<Transcript conversationState="bot" lines={IDLE_LINE_FOUR_MIN} />)

    expect(screen.getByText(IDLE_WARNING)).toBeInTheDocument()
  })

  test("hides the warning after a visitor message resets idle", () => {
    const { rerender } = renderWithProviders(
      <Transcript conversationState="bot" lines={IDLE_LINES_AT_FOUR_MIN} />,
    )
    expect(screen.getByText(IDLE_WARNING)).toBeInTheDocument()

    act(() => {
      rerender(<Transcript conversationState="bot" lines={IDLE_LINES_AFTER_VISITOR_REPLY} />)
    })

    expect(screen.queryByText(IDLE_WARNING)).not.toBeInTheDocument()
  })

  test("does not show the warning in prechat", () => {
    renderWithProviders(<Transcript conversationState="prechat" lines={IDLE_LINE_FOUR_MIN} />)

    expect(screen.queryByText(IDLE_WARNING)).not.toBeInTheDocument()
  })
})
