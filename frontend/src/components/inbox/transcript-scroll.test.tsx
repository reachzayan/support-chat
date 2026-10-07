import { fireEvent, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { TranscriptPane } from "./transcript-pane"
import type { InboxMessage } from "./types"

const message = (id: number, role: string, body: string): InboxMessage => ({
  id,
  role,
  body,
  created_at: "",
  author_user: null,
  source_article_ids: null,
  source_chunk_ids: null,
})

const messages = [
  message(10, "visitor", "Hello"),
  message(11, "agent", "How can I help?"),
  message(12, "visitor", "I have a question"),
]
const olderMessages = [message(9, "visitor", "Earlier question"), ...messages]
const incomingCases = ["visitor", "agent", "bot", "system"].map((role) => ({
  role,
  lines: [...messages, message(13, role, "Newest reply")],
}))

// jsdom has no layout engine; this viewport has 100px rows and a 100px visible area.
const installViewportLayout = (viewport: HTMLElement) => {
  const content = viewport.querySelector('[data-slot="message-scroller-content"]')!
  const rows = () =>
    Array.from(content.children).filter((row) => row.hasAttribute("data-message-id"))
  let top = 0
  Object.defineProperties(viewport, {
    clientHeight: { configurable: true, value: 100 },
    scrollHeight: { configurable: true, get: () => rows().length * 100 },
    scrollTop: {
      configurable: true,
      get: () => top,
      set: (value) => {
        top = value
      },
    },
    scrollTo: {
      configurable: true,
      value: ({ top: value }: ScrollToOptions) => {
        top = value ?? 0
      },
    },
  })
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
    function (this: HTMLElement) {
      const index = rows().indexOf(this)
      return new DOMRect(0, index < 0 ? 0 : index * 100 - top, 320, 100)
    },
  )
}

afterEach(() => vi.restoreAllMocks())

test.each(incomingCases)(
  "a new $role message brings the inbox to the bottom even after scrolling up",
  async ({ lines }) => {
    const view = renderWithProviders(<TranscriptPane lines={messages} />)
    const viewport = screen.getByRole("region", { name: "Messages" })
    installViewportLayout(viewport)
    await waitFor(() => expect(viewport.scrollTop).toBe(200))
    fireEvent.wheel(viewport, { deltaY: -100 })
    viewport.scrollTop = 0
    fireEvent.scroll(viewport)
    view.rerender(<TranscriptPane lines={lines} />)
    await waitFor(() => expect(viewport.scrollTop).toBe(300))
    expect(screen.getByRole("log", { name: "Transcript" })).toHaveTextContent("Newest reply")
  },
)

test("loading older history keeps the reader's position instead of jumping to the latest", async () => {
  const view = renderWithProviders(<TranscriptPane lines={messages} />)
  const viewport = screen.getByRole("region", { name: "Messages" })
  installViewportLayout(viewport)
  await waitFor(() => expect(viewport.scrollTop).toBe(200))
  fireEvent.wheel(viewport, { deltaY: -100 })
  viewport.scrollTop = 0
  fireEvent.scroll(viewport)
  view.rerender(<TranscriptPane lines={olderMessages} />)
  await waitFor(() => expect(viewport.scrollTop).toBe(100))
})
