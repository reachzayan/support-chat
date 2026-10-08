import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { SelectionContext } from "@/components/search/workspace-route"
import { renderWithProviders } from "@/test/render"

import { DataConsole } from "./data-console"
import { DataConsoleBody } from "./data-console-body"
import type { SubmissionRow } from "./data-shared"

const SEARCH_TARGET = { q: "alex@samplesite" }

const DEFAULT_VISITOR = {
  ip: "203.0.113.4",
  user_agent: "Chrome",
  geo_country: "US",
  geo_region: "NY",
  location: "New York, New York, United States",
  created_at: "2026-04-12T12:00:00Z",
} as const

const DEFAULT_PAGE = {
  title: "Results timing",
  url: "https://sample-site.example.com/results",
  referrer: "https://google.com",
} as const

const SUBMISSION_DEFAULTS: Omit<SubmissionRow, "id" | "visitor"> = {
  site_id: "samplesite",
  site_key: "samplesite",
  site_name: "SampleSite Support",
  state: "queued",
  inquiry_type: "results",
  intent: "timing",
  attention_needed: true,
  opening_message: "Question",
  assigned_agent: null,
  page: DEFAULT_PAGE,
  created_at: "2026-04-12T12:00:00Z",
  last_message_at: "2026-04-12T12:05:00Z",
  closed_at: null,
  blocked: false,
  block_id: null,
}

const submission = (
  overrides: Partial<SubmissionRow> & { id: string; name: string },
): SubmissionRow => ({
  ...SUBMISSION_DEFAULTS,
  ...overrides,
  opening_message: overrides.opening_message ?? `Question ${overrides.id}`,
  visitor:
    overrides.visitor ??
    ({
      ...DEFAULT_VISITOR,
      name: overrides.name,
      email: `${overrides.id}@example.com`,
      phone: null,
    } satisfies SubmissionRow["visitor"]),
})

const buildPagedRows = (count: number): SubmissionRow[] =>
  Array.from({ length: count }, (_, index) =>
    submission({
      id: `conversation-${index + 1}`,
      name: `Visitor ${index + 1}`,
      visitor: {
        ...DEFAULT_VISITOR,
        name: `Visitor ${index + 1}`,
        email: `visitor${index + 1}@example.com`,
        phone: null,
      },
    }),
  )

const stubSubmissions = (items: SubmissionRow[]) => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items }),
    }),
  )
}

const MIXED_ROWS: SubmissionRow[] = [
  submission({
    id: "alex",
    name: "Alex Chen",
    state: "queued",
    intent: "turnaround",
    site_id: "samplesite",
    site_name: "SampleSite Support",
    attention_needed: true,
    visitor: {
      ...DEFAULT_VISITOR,
      name: "Alex Chen",
      email: "alex@sample-site.example.com",
      phone: "555-0101",
    },
  }),
  submission({
    id: "blair",
    name: "Blair Diaz",
    state: "closed",
    site_id: "bgc",
    site_key: "bgc",
    site_name: "Sample Services",
    intent: "pricing",
    attention_needed: false,
    visitor: {
      ...DEFAULT_VISITOR,
      name: "Blair Diaz",
      email: "blair@sample-services.example.com",
      phone: null,
    },
  }),
  submission({
    id: "casey",
    name: "Casey Ortiz",
    state: "human",
    intent: "turnaround",
    attention_needed: true,
    visitor: {
      ...DEFAULT_VISITOR,
      name: "Casey Ortiz",
      email: "casey@sample-site.example.com",
      phone: "555-0103",
    },
  }),
]

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
        loadMoreError={false}
        loadingMore={false}
        onLoadMore={vi.fn()}
        onTranscript={vi.fn()}
      />,
    )

    expect(screen.getByLabelText("Loading submissions")).toBeInTheDocument()
  })
})

describe("data console table", () => {
  test("renders every loaded submission in the scrolling table", async () => {
    stubSubmissions(buildPagedRows(11))
    renderWithProviders(<DataConsole />)

    const table = await screen.findByRole("table", { name: "Form submissions" })
    expect(within(table).getAllByRole("columnheader")).toHaveLength(25)
    expect(within(table).getByRole("columnheader", { name: /Location/ })).toBeInTheDocument()
    expect(within(table).getAllByText("New York, New York, United States")).toHaveLength(11)
    expect(within(table).getByText("Visitor 1")).toBeInTheDocument()
    expect(within(table).getAllByText("Needs Attention").length).toBeGreaterThan(0)
    for (const badge of within(table).getAllByText("Needs Attention")) {
      expect(badge.className).toContain("whitespace-nowrap")
    }
    expect(within(table).getByText("Visitor 11")).toBeInTheDocument()
    expect(screen.getByText("11 of 11 loaded")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /Go to page/ })).not.toBeInTheDocument()
  })

  test("the submissions table keeps a permanent horizontal scrollbar", async () => {
    stubSubmissions(buildPagedRows(2))
    renderWithProviders(<DataConsole />)
    const table = await screen.findByRole("table", { name: "Form submissions" })
    expect(table.closest(".overflow-x-scroll")).not.toBeNull()
    expect(table.closest(".overflow-x-auto")).toBeNull()
  })
})

describe("data console filters", () => {
  test("state filter keeps only queued rows", async () => {
    stubSubmissions(MIXED_ROWS)
    renderWithProviders(<DataConsole />)
    const table = await screen.findByRole("table", { name: "Form submissions" })
    expect(within(table).getByText("Alex Chen")).toBeInTheDocument()
    expect(within(table).getByText("Blair Diaz")).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByLabelText("State"))
    await user.click(await screen.findByRole("option", { name: "Needs Attention" }))

    expect(within(table).getByText("Alex Chen")).toBeInTheDocument()
    expect(within(table).queryByText("Blair Diaz")).not.toBeInTheDocument()
    expect(within(table).queryByText("Casey Ortiz")).not.toBeInTheDocument()
    expect(screen.getByText("1 of 3 loaded")).toBeInTheDocument()
  })

  test("site filter keeps only Sample Services", async () => {
    stubSubmissions(MIXED_ROWS)
    renderWithProviders(<DataConsole />)
    const table = await screen.findByRole("table", { name: "Form submissions" })

    const user = userEvent.setup()
    await user.click(screen.getByLabelText("Site"))
    await user.click(await screen.findByRole("option", { name: "Sample Services" }))

    expect(within(table).getByText("Blair Diaz")).toBeInTheDocument()
    expect(within(table).queryByText("Alex Chen")).not.toBeInTheDocument()
    expect(within(table).queryByText("Casey Ortiz")).not.toBeInTheDocument()
  })

  test("intent filter keeps Alex and Casey on turnaround", async () => {
    stubSubmissions(MIXED_ROWS)
    renderWithProviders(<DataConsole />)
    const table = await screen.findByRole("table", { name: "Form submissions" })

    const user = userEvent.setup()
    await user.click(screen.getByLabelText("Intent"))
    await user.click(await screen.findByRole("option", { name: "Turnaround" }))

    expect(within(table).getByText("Alex Chen")).toBeInTheDocument()
    expect(within(table).getByText("Casey Ortiz")).toBeInTheDocument()
    expect(within(table).queryByText("Blair Diaz")).not.toBeInTheDocument()
  })

  test("a retained search URL filters submissions by email", async () => {
    stubSubmissions(MIXED_ROWS)
    renderWithProviders(
      <SelectionContext.Provider value={SEARCH_TARGET}>
        <DataConsole />
      </SelectionContext.Provider>,
    )
    const table = await screen.findByRole("table", { name: "Form submissions" })

    expect(within(table).getByText("Alex Chen")).toBeInTheDocument()
    expect(within(table).queryByText("Blair Diaz")).not.toBeInTheDocument()
    expect(within(table).queryByText("Casey Ortiz")).not.toBeInTheDocument()
  })
})

describe("data console sorting", () => {
  test("sorting by name ascending lists Alex then Blair then Casey", async () => {
    stubSubmissions([MIXED_ROWS[1], MIXED_ROWS[2], MIXED_ROWS[0]])
    renderWithProviders(<DataConsole />)
    const table = await screen.findByRole("table", { name: "Form submissions" })
    await screen.findByText("Blair Diaz")

    await userEvent.setup().click(screen.getByRole("button", { name: "Sort by Name" }))

    expect(screen.getByRole("columnheader", { name: /Name/ })).toHaveAttribute(
      "aria-sort",
      "ascending",
    )
    expect(screen.getByRole("columnheader", { name: /Email/ })).toHaveAttribute("aria-sort", "none")
    expect(screen.getByRole("button", { name: "Sort by Email" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Sort by Phone" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Sort by Site" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Sort by User agent" })).not.toBeInTheDocument()
    const names = within(table)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[0]?.textContent)
    expect(names).toEqual(["Alex Chen", "Blair Diaz", "Casey Ortiz"])
  })
})

describe("data console export", () => {
  test("export modal sends selected columns, dates, and site", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (
        url.startsWith("/api/conversations/submissions?") ||
        url === "/api/conversations/submissions"
      ) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ items: MIXED_ROWS }),
        }
      }
      if (url === "/api/sites") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ id: "samplesite", name: "SampleSite Support" }],
          }),
        }
      }
      if (url === "/api/conversations/submissions/export") {
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob(["Name\nAlex Chen"], { type: "text/csv" }),
        }
      }
      return { ok: false, status: 404, json: async () => ({}) }
    })
    vi.stubGlobal("fetch", fetchMock)
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: () => "blob:export",
      revokeObjectURL: vi.fn(),
    })
    renderWithProviders(<DataConsole />)
    await screen.findByText("Alex Chen")
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "Export" }))
    expect(await screen.findByRole("heading", { name: "Export submissions" })).toBeInTheDocument()
    await user.click(screen.getByRole("checkbox", { name: "Email" }))
    await user.type(screen.getByLabelText("Export from date"), "2026-09-01")
    await user.type(screen.getByLabelText("Export to date"), "2026-09-10")
    await user.click(screen.getByLabelText("Export site"))
    await user.click(await screen.findByRole("option", { name: "SampleSite Support" }))
    await user.click(screen.getByRole("button", { name: "Download" }))
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([request]) => String(request) === "/api/conversations/submissions/export",
        ),
      ).toBe(true)
    })
    const exportCall = fetchMock.mock.calls.find(
      ([request]) => String(request) === "/api/conversations/submissions/export",
    )
    const body = JSON.parse(String(exportCall?.[1]?.body)) as {
      columns: string[]
      site_id: string | null
      date_from: string | null
      date_to: string | null
    }
    expect(body.site_id).toBe("samplesite")
    expect(body.date_from).toBe("2026-09-01")
    expect(body.date_to).toBe("2026-09-10")
    expect(body.columns).toContain("Name")
    expect(body.columns).not.toContain("Email")
    expect(body.columns).not.toContain("Transcript")
  })
})

describe("data console block", () => {
  test("block action posts the checked identifiers for that visitor", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.startsWith("/api/conversations/submissions")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ items: MIXED_ROWS }),
        }
      }
      if (url === "/api/visitor-blocks" && init?.method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({ id: "block-1" }),
        }
      }
      return { ok: false, status: 404, json: async () => ({}) }
    })
    vi.stubGlobal("fetch", fetchMock)
    renderWithProviders(<DataConsole />)
    await screen.findByText("Alex Chen")
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "Block Blair Diaz" }))
    expect(await screen.findByRole("heading", { name: "Block visitor" })).toBeInTheDocument()
    expect(screen.getByRole("checkbox", { name: /Phone/ })).toBeDisabled()
    await user.click(screen.getByRole("checkbox", { name: /IP/ }))
    await user.click(screen.getByRole("button", { name: "Block visitor" }))
    await waitFor(() => expect(screen.getByText("Visitor blocked.")).toBeInTheDocument())
    const blockCall = fetchMock.mock.calls.find(
      ([request, init]) => String(request) === "/api/visitor-blocks" && init?.method === "POST",
    )
    expect(JSON.parse(String(blockCall?.[1]?.body))).toEqual({
      site_id: "bgc",
      email: "blair@sample-services.example.com",
      phone: null,
      ip: null,
    })
    expect(screen.getByRole("button", { name: "Unblock Blair Diaz" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Block Blair Diaz" })).not.toBeInTheDocument()
  })
})

describe("data console unblock", () => {
  test("unblock action deletes the block for that visitor", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.startsWith("/api/conversations/submissions")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: MIXED_ROWS.map((row) => {
              if (row.id !== "blair") {
                return row
              }
              return Object.assign({}, row, { blocked: true, block_id: "block-1" })
            }),
          }),
        }
      }
      if (url === "/api/visitor-blocks/block-1" && init?.method === "DELETE") {
        return { ok: true, status: 204, json: async () => ({}) }
      }
      return { ok: false, status: 404, json: async () => ({}) }
    })
    vi.stubGlobal("fetch", fetchMock)
    renderWithProviders(<DataConsole />)
    await screen.findByText("Alex Chen")
    expect(screen.getByRole("button", { name: "Unblock Blair Diaz" })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: "Unblock Blair Diaz" }))
    await waitFor(() => expect(screen.getByText("Visitor unblocked.")).toBeInTheDocument())
    expect(screen.getByRole("button", { name: "Block Blair Diaz" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Unblock Blair Diaz" })).not.toBeInTheDocument()
  })
})
