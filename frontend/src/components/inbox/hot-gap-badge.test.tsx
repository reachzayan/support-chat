import { act, screen } from "@testing-library/react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { HotGapBadge } from "./hot-gap-badge"

const CONVERSATION = "99999999-9999-4999-8999-999999999999"

const stubBadge = (body: unknown, status = 200) => {
  setAccessToken("staff-token")
  const json = vi.fn(async () => body)
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: status === 200, status, json })),
  )
  return json
}

describe("inbox hot-question badge", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("links agents to the queue when this chat is part of a repeated question", async () => {
    stubBadge({
      gap: { id: "g", question: "How do I enroll a driver?", conversations: 7, spiking: false },
    })
    renderWithProviders(<HotGapBadge conversationId={CONVERSATION} />)

    const link = await screen.findByRole("link", { name: /Repeated question/ })

    expect(link).toHaveAttribute("href", "/admin/suggested-faqs")
    expect(link).toHaveTextContent("Asked in 7 chats")
  })

  test("says when the question is spiking", async () => {
    stubBadge({ gap: { id: "g", question: "Q?", conversations: 3, spiking: true } })
    renderWithProviders(<HotGapBadge conversationId={CONVERSATION} />)

    expect(await screen.findByRole("link", { name: /Spiking/ })).toBeInTheDocument()
  })

  test("renders nothing, instead of crashing the inbox, when the answer has no gap field", async () => {
    const json = stubBadge({})
    renderWithProviders(<HotGapBadge conversationId={CONVERSATION} />)

    await vi.waitFor(() => expect(json).toHaveBeenCalled())
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.queryByRole("link")).toBeNull()
  })

  test("renders nothing for an ordinary chat, and nothing when the lookup fails", async () => {
    stubBadge({ gap: null })
    const { unmount } = renderWithProviders(<HotGapBadge conversationId={CONVERSATION} />)
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
    expect(screen.queryByRole("link")).toBeNull()
    unmount()

    stubBadge({ detail: "broken" }, 500)
    renderWithProviders(<HotGapBadge conversationId={CONVERSATION} />)
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled())
    expect(screen.queryByRole("link")).toBeNull()
  })
})
