/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-array-as-prop -- Card fields and actions are built per record. */

import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"
import { setViewportWidth } from "@/test/viewport"

import { BlockedConsole } from "./blocked/blocked-console"
import { DataConsoleBody } from "./data/data-console-body"
import type { SubmissionRow } from "./data/data-shared"
import { LogsConsole } from "./logs/logs-console"
import { SitesConsole } from "./sites/sites-console"
import { mockListFetch, SNIPPET } from "./sites/sites-test-fixtures"

let restoreViewport: () => void = () => {}

beforeEach(() => {
  restoreViewport = setViewportWidth(375)
  setAccessToken("staff-token")
})

afterEach(() => {
  restoreViewport()
  vi.unstubAllGlobals()
})

describe("sites on a phone", () => {
  test("rows become cards with a real Manage button and no sideways table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    const list = await screen.findByRole("list", { name: "Sites" })
    expect(screen.queryByRole("table", { name: "Sites" })).not.toBeInTheDocument()
    const card = within(list).getByRole("listitem")
    expect(within(card).getByText("SampleSite Support")).toBeInTheDocument()
    expect(within(card).getByText("Site key")).toBeInTheDocument()
    expect(within(card).getByText("samplesite")).toBeInTheDocument()
    expect(within(card).getByText("Bot on")).toBeInTheDocument()
    expect(within(card).getByRole("button", { name: "Copy snippet" })).toBeInTheDocument()
    await user.click(within(card).getByRole("button", { name: "Manage" }))
    expect(await screen.findByText(SNIPPET.split("\n")[0]!, { exact: false })).toBeInTheDocument()
  })

  test("desktop keeps the table and lets keyboard users open a site from its name", async () => {
    restoreViewport()
    restoreViewport = setViewportWidth(1280)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)
    const table = await screen.findByRole("table", { name: "Sites" })
    expect(screen.queryByRole("list", { name: "Sites" })).not.toBeInTheDocument()
    const nameButton = within(table).getByRole("button", { name: "SampleSite Support" })
    nameButton.focus()
    await userEvent.setup().keyboard("{Enter}")
    expect(await screen.findByRole("dialog")).toBeInTheDocument()
  })
})

const SUBMISSION: SubmissionRow = {
  id: "c1",
  site_id: "easy",
  site_key: "easy",
  site_name: "SampleSite Support",
  state: "queued",
  inquiry_type: "results",
  intent: "timing",
  attention_needed: true,
  opening_message: "How long do results take?",
  assigned_agent: null,
  visitor: {
    name: "Sample User",
    email: "user@example.com",
    phone: null,
    ip: "203.0.113.4",
    user_agent: "Chrome",
    geo_country: "US",
    geo_region: "NY",
    location: null,
    created_at: "2026-04-12T12:00:00Z",
  },
  page: { title: null, url: null, referrer: null },
  created_at: "2026-04-12T12:00:00Z",
  last_message_at: "2026-04-12T12:05:00Z",
  closed_at: null,
  blocked: false,
  block_id: null,
}

describe("data on a phone", () => {
  test("submissions render as cards with Transcript and Block actions", async () => {
    const onTranscript = vi.fn()
    renderWithProviders(
      <DataConsoleBody
        rows={[SUBMISSION]}
        loadError={false}
        hasMore={false}
        loadMoreError={false}
        loadingMore={false}
        onLoadMore={vi.fn()}
        onTranscript={onTranscript}
      />,
    )
    const list = await screen.findByRole("list", { name: "Form submissions" })
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(within(list).getByText("user@example.com")).toBeInTheDocument()
    expect(within(list).getByText("How long do results take?")).toBeInTheDocument()
    await userEvent
      .setup()
      .click(within(list).getByRole("button", { name: "Transcript for Sample User" }))
    expect(onTranscript).toHaveBeenCalledWith("c1")
    expect(within(list).getByRole("button", { name: "Block Sample User" })).toBeInTheDocument()
  })
})

describe("data on desktop", () => {
  test("emails stay on one line with a tooltip, and the first column is sticky", async () => {
    restoreViewport()
    restoreViewport = setViewportWidth(1440)
    renderWithProviders(
      <DataConsoleBody
        rows={[SUBMISSION]}
        loadError={false}
        hasMore={false}
        loadMoreError={false}
        loadingMore={false}
        onLoadMore={vi.fn()}
        onTranscript={vi.fn()}
      />,
    )
    const table = await screen.findByRole("table", { name: "Form submissions" })
    const email = within(table).getByText("user@example.com")
    expect(email).toHaveAttribute("title", "user@example.com")
    expect(email).toHaveClass("whitespace-nowrap", "text-ellipsis")
    expect(within(table).getByText("Sample User")).toHaveClass("sticky", "left-0")
    expect(within(table).getByRole("columnheader", { name: /Name/ })).toHaveClass(
      "sticky",
      "left-0",
    )
  })
})

describe("logs on a phone", () => {
  test("log entries render as labelled cards", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            {
              id: "l1",
              created_at: "2026-10-02T15:25:00Z",
              level: "error",
              source: "backend",
              logger_name: "app",
              event: "ingest_page_failed",
              message: "Fetch timed out",
              detail: { page: "faq" },
            },
          ],
        }),
      }),
    )
    renderWithProviders(<LogsConsole isAdmin={false} displayName="Riley" />)
    const list = await screen.findByRole("list", { name: "Application logs" })
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(within(list).getByText("ingest_page_failed")).toBeInTheDocument()
    expect(within(list).getByText("Message")).toBeInTheDocument()
    expect(within(list).getByText("Fetch timed out")).toBeInTheDocument()
  })
})

describe("blocked on a phone", () => {
  test("blocked visitors render as cards with an Unblock button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            {
              id: "b1",
              site_id: "easy",
              site_name: "SampleSite",
              ip: "203.0.113.40",
              email: "ada@example.com",
              phone: null,
              created_by_name: "Alex Morgan",
              created_at: "2026-09-29T12:00:00Z",
            },
          ],
        }),
      }),
    )
    renderWithProviders(<BlockedConsole />)
    const list = await screen.findByRole("list", { name: "Blocked visitors" })
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(within(list).getByText("ada@example.com")).toBeInTheDocument()
    expect(within(list).getByText("203.0.113.40")).toBeInTheDocument()
    expect(
      within(list).getByRole("button", { name: "Unblock visitor on SampleSite" }),
    ).toBeInTheDocument()
  })
})
