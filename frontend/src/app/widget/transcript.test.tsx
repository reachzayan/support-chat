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
const RESET_RESUME_LINES = [
  { id: 8, role: "system", body: "This chat was reset by the visitor." },
  { id: 9, role: "system", body: "This chat has been resumed." },
]

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

  test("reset and resume notes sit in the middle without an agent label", () => {
    renderWithProviders(<Transcript selfRole="agent" lines={RESET_RESUME_LINES} />)

    expect(screen.queryByText("Agent")).not.toBeInTheDocument()
    expect(
      screen.getByText("This chat was reset by the visitor.").closest('[data-slot="marker"]'),
    ).toHaveAttribute("data-variant", "separator")
    expect(
      screen.getByText("This chat has been resumed.").closest('[data-slot="marker"]'),
    ).toHaveAttribute("data-variant", "separator")
  })

  test("keeps lifecycle notices centered while treating other system copy as an agent message", () => {
    renderWithProviders(<Transcript lines={MIXED_LINES} />)

    expect(screen.queryByText("You")).not.toBeInTheDocument()
    expect(screen.queryByRole("img")).not.toBeInTheDocument()
    expect(document.querySelector('[data-slot="message-avatar"]')).toBeNull()
    expect(screen.getByText(VISITOR_LINE).closest('[data-slot="message"]')).toHaveAttribute(
      "data-align",
      "end",
    )
    expect(screen.getByText("Agent")).toBeInTheDocument()
    expect(
      screen.getByText("Your application is being reviewed.").closest('[data-slot="message"]'),
    ).toHaveAttribute("data-align", "start")
    expect(screen.getByText("A human has joined.").closest('[data-slot="marker"]')).toHaveAttribute(
      "data-variant",
      "separator",
    )
  })

  test("keeps paragraph breaks in agent replies", () => {
    renderWithProviders(<Transcript lines={AGENT_REPLY_LINES} />)

    expect(
      screen.getByText(/Random programs nationwide/).closest('[data-slot="bubble-content"]'),
    ).toHaveClass("whitespace-pre-wrap")
  })

  test("follows a newly received message inside the messages region", () => {
    const { rerender } = renderWithProviders(<Transcript autoFollow lines={VISITOR_LINES} />)

    rerender(<Transcript autoFollow lines={FOLLOW_UP_LINES} />)

    const reply = screen.getByText("Your result is ready.")
    expect(screen.getByRole("region", { name: "Messages" })).toContainElement(reply)
    expect(reply.closest('[data-slot="message"]')).toHaveAttribute("data-align", "start")
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

const CITATION_LINES = [
  {
    id: 4,
    role: "bot" as const,
    body: "SampleMail verifies every address before mailing.",
    source_urls: ["https://sample-data.example.com/samplemail"],
    citations: [
      {
        source_urls: ["https://sample-data.example.com/samplemail"],
        source_title: "SampleMail",
        cited_text: "SampleMail verifies every address before the piece enters the mailstream.",
      },
    ],
  },
]

describe("transcript citations", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    })
  })

  test("labels a page citation with the page title and does not quote the passage", () => {
    renderWithProviders(<Transcript lines={CITATION_LINES} />)

    expect(screen.getByRole("button", { name: "SampleMail: SampleMail" })).toBeInTheDocument()
    expect(screen.queryByText("Source 1")).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        "“SampleMail verifies every address before the piece enters the mailstream.”",
      ),
    ).not.toBeInTheDocument()
  })
})
