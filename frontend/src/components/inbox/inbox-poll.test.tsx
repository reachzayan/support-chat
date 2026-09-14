import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { InboxConsole } from "@/components/inbox/inbox-console"
import { renderWithProviders } from "@/test/render"

import {
  ALEX,
  CONVO_ID,
  OTHER_CONVO,
  adaDetail,
  adaQueued,
  bgDetail,
  bgQueued,
  emit,
  FakeSocket,
  resetInboxHarness,
  setDetails,
  setListCursor,
  setListItems,
} from "./inbox-test-harness"

describe("inbox scheduled poll", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("scheduled list refetch shows a new conversation once without inbox_upsert", async () => {
    setListItems([])
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      renderWithProviders(<InboxConsole user={ALEX} />)
      await user.click(screen.getByRole("button", { name: "Needs Attention" }))
      expect(screen.queryByText("Ada Lopez")).not.toBeInTheDocument()
      setListItems([adaQueued])
      await vi.advanceTimersByTimeAsync(15_000)
      await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
      expect(screen.getAllByText("Ada Lopez")).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("inbox load more", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("Load more appends the next cursor page", async () => {
    setListCursor("page-2")
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    await user.click(screen.getByRole("button", { name: "Needs Attention" }))
    await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: "Load more" }))
    await waitFor(() => expect(screen.getByText("Third Visitor")).toBeInTheDocument())
    expect(screen.getByText("Ada Lopez")).toBeInTheDocument()
  })

  test("rapid load more clicks keep one copy of each conversation", async () => {
    setListCursor("page-2")
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    await user.click(screen.getByRole("button", { name: "Needs Attention" }))
    await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
    const loadMore = screen.getByRole("button", { name: "Load more" })
    await user.click(loadMore)
    await user.click(loadMore)
    await waitFor(() => expect(screen.getByText("Third Visitor")).toBeInTheDocument())
    expect(screen.getAllByText("Third Visitor")).toHaveLength(1)
  })

  test("scheduled poll after Load more keeps the second page", async () => {
    setListCursor("page-2")
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      renderWithProviders(<InboxConsole user={ALEX} />)
      await user.click(screen.getByRole("button", { name: "Needs Attention" }))
      await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
      await user.click(screen.getByRole("button", { name: "Load more" }))
      await waitFor(() => expect(screen.getByText("Third Visitor")).toBeInTheDocument())
      const callsBeforePoll = vi.mocked(fetch).mock.calls.length
      await vi.advanceTimersByTimeAsync(15_000)
      await waitFor(() =>
        expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(callsBeforePoll),
      )
      expect(screen.getByText("Third Visitor")).toBeInTheDocument()
      expect(screen.getByText("Ada Lopez")).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("inbox view counts", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("Live, Bot, Needs Attention, and Closed show their counts without clicking a view", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveTextContent("2"),
    )
    expect(screen.getByRole("button", { name: "Live" })).toHaveTextContent("0")
    expect(screen.getByRole("button", { name: "Bot" })).toHaveTextContent("0")
    expect(screen.getByRole("button", { name: "Closed" })).toHaveTextContent("0")
  })

  test("inbox_upsert refreshes an unselected view count", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveTextContent("2"),
    )
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    setListItems([
      adaQueued,
      bgQueued,
      {
        id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
        visitor_display: "Bot Visitor",
        site_name: "SampleSite",
        state: "bot",
        preview: "How fast are results?",
        last_message_at: "2026-09-09T16:05:00+00:00",
        assigned_agent: null,
      },
    ])
    emit(FakeSocket.instances[0], {
      v: 1,
      type: "inbox_upsert",
      conversation_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      state: "bot",
      site_key: "samplesite",
    })
    await waitFor(() => expect(screen.getByRole("button", { name: "Bot" })).toHaveTextContent("1"))
    expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveTextContent("2")
  })
})

describe("inbox transcript poll", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("scheduled poll shows a new visitor line in the open transcript", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      renderWithProviders(<InboxConsole user={ALEX} />)
      await user.click(screen.getByRole("button", { name: "Needs Attention" }))
      await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
      await user.click(screen.getByRole("button", { name: /Ada Lopez/ }))
      await waitFor(() => expect(screen.getByText("ada@example.com")).toBeInTheDocument())
      expect(screen.queryByText("Please confirm the portal login.")).not.toBeInTheDocument()
      setDetails({
        [CONVO_ID]: {
          ...adaDetail,
          messages: [
            ...adaDetail.messages,
            {
              id: 2,
              role: "visitor",
              author_user: null,
              body: "Please confirm the portal login.",
              source_article_ids: null,
              source_chunk_ids: null,
              created_at: "2026-09-09T16:01:00+00:00",
            },
          ],
        },
        [OTHER_CONVO]: bgDetail,
      })
      await vi.advanceTimersByTimeAsync(15_000)
      await waitFor(() =>
        expect(screen.getByText("Please confirm the portal login.")).toBeInTheDocument(),
      )
    } finally {
      vi.useRealTimers()
    }
  })
})
