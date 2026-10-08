import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { StatusBoard } from "./status-board"

const DAYS_ANSWERING = Array.from({ length: 30 }, () => "up")
const POSTGRES_BARS = [...Array.from({ length: 28 }, () => "up"), "degraded", "up"]
const QUIET_LATENCY = Array.from({ length: 24 }, () => null)
const POSTGRES_LATENCY = [...Array.from({ length: 20 }, () => null), 10, 20, 42, 12]

const monitor = (
  key: string,
  name: string,
  extra: { availability_30d?: string[]; latency_24h?: (number | null)[] } = {},
) => ({
  key,
  name,
  state: "ok",
  availability_30d: extra.availability_30d ?? DAYS_ANSWERING,
  latency_24h: extra.latency_24h ?? QUIET_LATENCY,
})

const SNAPSHOT = {
  checked_at: "2026-10-02T15:35:00Z",
  overall: "attention",
  headline: "Knowledge ingest failed",
  services: {
    api: "ok",
    postgres: "ok",
    redis: "ok",
    worker: "ok",
  },
  live: { visitors: 2, specialists: 1 },
  inbox: { waiting: 3, bot: 5, live: 1, closed_today: 4 },
  knowledge: { ready: 1, running: 0, failed: 1, queued: 0 },
  gaps_open: 7,
  errors_24h: 2,
  recent_errors: [
    {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      created_at: "2026-10-02T15:25:00Z",
      event: "ingest_page_failed",
      message: "Fetch timed out for knowledge page",
      source: "backend",
    },
    {
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      created_at: "2026-10-02T14:55:00Z",
      event: "ui_window_error",
      message: "Unhandled window error",
      source: "frontend",
    },
  ],
  sites: [
    {
      id: "11111111-1111-4111-8111-111111111111",
      key: "samplesite",
      name: "SampleSite",
      enabled: true,
      bot_enabled: true,
      human_enabled: true,
      widget_installed: true,
      waiting: 3,
      knowledge: "failed",
    },
    {
      id: "22222222-2222-4222-8222-222222222222",
      key: "backgroundchecks",
      name: "Sample Services",
      enabled: true,
      bot_enabled: true,
      human_enabled: true,
      widget_installed: null,
      waiting: 0,
      knowledge: "ready",
    },
  ],
  uptime: { hours_24: 100, days_7: 99.8, days_30: 99.8, days_90: 99.8 },
  monitors: [
    monitor("api", "API"),
    monitor("postgres", "Postgres", {
      availability_30d: POSTGRES_BARS,
      latency_24h: POSTGRES_LATENCY,
    }),
    monitor("redis", "Redis"),
    monitor("worker", "Background work"),
  ],
  incidents: [
    { date: "2026-10-02", summary: "No incidents" },
    { date: "2026-10-01", summary: "Postgres was down" },
    { date: "2026-09-30", summary: "No incidents" },
    { date: "2026-09-29", summary: "No incidents" },
    { date: "2026-09-28", summary: "No incidents" },
    { date: "2026-09-27", summary: "No incidents" },
    { date: "2026-09-26", summary: "No incidents" },
  ],
}

const jsonResponse = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

const loadCount = (label: string, value: string) =>
  expect(within(screen.getByRole("article", { name: label })).getByText(value)).toBeInTheDocument()

const websiteRow = (name: RegExp) =>
  within(screen.getByRole("table", { name: "Websites" })).getByRole("row", { name })

describe("status board desk", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("reads the desk snapshot: headline, waiting chats, failed knowledge, and errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SNAPSHOT)))

    renderWithProviders(<StatusBoard />)

    expect(
      await screen.findByRole("heading", { name: "Knowledge ingest failed" }),
    ).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Status" })).toBeInTheDocument()
    loadCount("Waiting", "3")
    loadCount("With the assistant", "5")
    loadCount("With a specialist", "1")
    loadCount("Closed today", "4")
    expect(screen.getByText("2 visitors on the widget")).toBeInTheDocument()
    expect(screen.getByText("1 specialist connected")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "7 unanswered questions" })).toHaveAttribute(
      "href",
      "/admin/suggested-faqs",
    )

    const easy = websiteRow(/SampleSite/)
    expect(within(easy).getByText("Failed")).toBeInTheDocument()
    expect(within(easy).getByText("Installed")).toBeInTheDocument()
    expect(within(easy).getByText("3 waiting")).toBeInTheDocument()
    const background = websiteRow(/Sample Services/)
    expect(within(background).getByText("Ready")).toBeInTheDocument()
    expect(within(background).getByText("Not seen")).toBeInTheDocument()

    expect(screen.getByText("ingest_page_failed")).toBeInTheDocument()
    expect(screen.getByText("Fetch timed out for knowledge page")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Application logs" })).toHaveAttribute(
      "href",
      "/admin/logs",
    )
  })

  test("a failed load tells the specialist to retry, then shows the board", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse(SNAPSHOT))
    vi.stubGlobal("fetch", fetchStub)

    renderWithProviders(<StatusBoard />)

    expect(await screen.findByText("Status could not be loaded.")).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Knowledge ingest failed" }),
    ).not.toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }))

    expect(
      await screen.findByRole("heading", { name: "Knowledge ingest failed" }),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole("article", { name: "Waiting" })).getByText("3"),
    ).toBeInTheDocument()
  })

  test("Refresh replaces the waiting count with the latest snapshot", async () => {
    const next = {
      ...SNAPSHOT,
      inbox: { ...SNAPSHOT.inbox, waiting: 1 },
      sites: SNAPSHOT.sites.map((site) =>
        site.key === "samplesite" ? { ...site, waiting: 1 } : site,
      ),
    }
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(SNAPSHOT))
      .mockResolvedValueOnce(jsonResponse(next))
    vi.stubGlobal("fetch", fetchStub)

    renderWithProviders(<StatusBoard />)
    expect(
      within(await screen.findByRole("article", { name: "Waiting" })).getByText("3"),
    ).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh" }))

    await waitFor(() =>
      expect(
        within(screen.getByRole("article", { name: "Waiting" })).getByText("1"),
      ).toBeInTheDocument(),
    )
  })
})

describe("status board uptime", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("period cards show 100% and 99.8% uptime from the snapshot", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SNAPSHOT)))

    renderWithProviders(<StatusBoard />)

    expect(await screen.findByRole("status")).toHaveTextContent("Knowledge ingest failed")
    loadCount("Last 24 hours", "100%")
    loadCount("Last 7 days", "99.8%")
    loadCount("Last 30 days", "99.8%")
    loadCount("Last 90 days", "99.8%")
    expect(screen.getByText("Last updated 02 Oct 2026, 15:35 UTC")).toBeInTheDocument()
    expect(screen.getByText("Next update in 15 seconds")).toBeInTheDocument()
  })

  test("Postgres shows a 30-day tape with one degraded day and a 42 ms peak", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SNAPSHOT)))

    renderWithProviders(<StatusBoard />)

    const row = within(await screen.findByRole("row", { name: /Postgres/ }))
    expect(
      row.getByLabelText("Availability last 30 days: 29 days answering, 1 day degraded"),
    ).toBeInTheDocument()
    expect(
      row.getByLabelText("Median response last 24 hours, peak 42 milliseconds"),
    ).toBeInTheDocument()
  })

  test("incidents lists 1 Oct as Postgres down and the other six days as clear", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SNAPSHOT)))

    renderWithProviders(<StatusBoard />)

    expect(await screen.findByRole("heading", { name: "Incidents" })).toBeInTheDocument()
    const days = screen.getByRole("list", { name: "Incidents" })
    expect(within(days).getByText("2026-10-01")).toBeInTheDocument()
    expect(within(days).getByText("Postgres was down")).toBeInTheDocument()
    expect(within(days).getAllByText("No incidents")).toHaveLength(6)
  })

  test("Refresh replaces 24-hour uptime with the latest snapshot", async () => {
    const next = {
      ...SNAPSHOT,
      uptime: { ...SNAPSHOT.uptime, hours_24: 99.8 },
    }
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(SNAPSHOT))
      .mockResolvedValueOnce(jsonResponse(next))
    vi.stubGlobal("fetch", fetchStub)

    renderWithProviders(<StatusBoard />)
    expect(
      within(await screen.findByRole("article", { name: "Last 24 hours" })).getByText("100%"),
    ).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh" }))

    await waitFor(() =>
      expect(
        within(screen.getByRole("article", { name: "Last 24 hours" })).getByText("99.8%"),
      ).toBeInTheDocument(),
    )
  })
})

describe("status board table scroll", () => {
  test("service and website tables keep a permanent horizontal scrollbar", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SNAPSHOT)))
    renderWithProviders(<StatusBoard />)
    const services = await screen.findByRole("table", { name: "Services" })
    const websites = screen.getByRole("table", { name: "Websites" })
    expect(services.closest(".overflow-x-scroll")).not.toBeNull()
    expect(services.closest(".overflow-x-auto")).toBeNull()
    expect(websites.closest(".overflow-x-scroll")).not.toBeNull()
    expect(websites.closest(".overflow-x-auto")).toBeNull()
  })
})
