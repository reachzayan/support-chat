import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { DataConsole } from "./data-console"
import { DataConsoleBody } from "./data-console-body"

describe("data console errors", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({}),
      }),
    )
  })

  test("shows a load error instead of the empty submissions state", async () => {
    renderWithProviders(<DataConsole />)
    await waitFor(() => expect(screen.getByText("Could not load submissions.")).toBeInTheDocument())
    expect(screen.queryByText("No form submissions yet")).not.toBeInTheDocument()
  })
})

describe("data console body", () => {
  test("shows a skeleton while submissions are loading", () => {
    renderWithProviders(
      <DataConsoleBody
        rows={null}
        loadError={false}
        hasMore={false}
        loadingMore={false}
        onLoadMore={vi.fn()}
        onTranscript={vi.fn()}
      />,
    )

    expect(screen.getByLabelText("Loading submissions")).toBeInTheDocument()
  })
})

describe("data console table", () => {
  test("renders every submission field in a paginated shadcn table", async () => {
    const rows = Array.from({ length: 11 }, (_, index) => ({
      id: `conversation-${index + 1}`,
      site_id: "site-1",
      site_key: "samplesite",
      site_name: "SampleSite Support",
      state: "queued",
      inquiry_type: "results",
      intent: "timing",
      attention_needed: true,
      opening_message: `Question ${index + 1}`,
      assigned_agent: null,
      visitor: {
        name: `Visitor ${index + 1}`,
        email: `visitor${index + 1}@example.com`,
        phone: null,
        ip: "203.0.113.4",
        user_agent: "Chrome",
        geo_country: "US",
        geo_region: "NY",
        location: "New York, New York, United States",
        created_at: "2026-04-12T12:00:00Z",
      },
      page: {
        title: "Results timing",
        url: "https://sample-site.example.com/results",
        referrer: "https://google.com",
      },
      created_at: "2026-04-12T12:00:00Z",
      last_message_at: "2026-04-12T12:05:00Z",
      closed_at: null,
    }))
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: rows }),
      }),
    )

    renderWithProviders(<DataConsole />)

    const table = await screen.findByRole("table", { name: "Form submissions" })
    expect(within(table).getAllByRole("columnheader")).toHaveLength(24)
    expect(within(table).getByRole("columnheader", { name: /Location/ })).toBeInTheDocument()
    expect(within(table).getAllByText("New York, New York, United States")).toHaveLength(10)
    expect(within(table).getByText("Visitor 1")).toBeInTheDocument()
    expect(within(table).getAllByText("Needs Attention").length).toBeGreaterThan(0)
    expect(within(table).queryByText("Visitor 11")).not.toBeInTheDocument()
    expect(screen.getByText("11 loaded submissions")).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole("link", { name: "Go to page 2" }))

    expect(within(table).getByText("Visitor 11")).toBeInTheDocument()
    expect(within(table).queryByText("Visitor 1")).not.toBeInTheDocument()
  })
})
