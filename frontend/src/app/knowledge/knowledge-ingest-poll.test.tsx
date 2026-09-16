import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import {
  createIngestQueuedFetch,
  createFailedProgressFetch,
  createSelectedPagePollFetch,
  DOT_COPY,
  TIMING_COPY,
} from "./knowledge-ingest-queued-fetch"
import {
  jsonOk,
  PAGE_ID,
  PAGE_TITLE,
  PAGE_URL,
  siteRecord,
  SITE_ID,
  SOURCE_ID,
} from "./knowledge-test-fetch"

describe("knowledge ingest queued", () => {
  test("queued source becomes ready and lists the ingested page", async () => {
    const { fetchFn, markIngested } = createIngestQueuedFetch()
    vi.stubGlobal("fetch", vi.fn(fetchFn))
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
      await waitFor(() => expect(screen.getByText("Queued")).toBeInTheDocument())
      expect(screen.queryByText(PAGE_TITLE)).not.toBeInTheDocument()
      markIngested()
      await vi.advanceTimersByTimeAsync(2_000)
      await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument())
      await waitFor(() =>
        expect(screen.getByRole("button", { name: PAGE_TITLE })).toBeInTheDocument(),
      )
      const indexedLabel = screen.getByText("Indexed pages")
      expect(indexedLabel.parentElement?.querySelector(".tabular-nums")).toHaveTextContent("1")
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("knowledge ingest selection", () => {
  test("polling after ingest keeps the selected page", async () => {
    vi.stubGlobal("fetch", vi.fn(createSelectedPagePollFetch()))
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
      await waitFor(() => expect(screen.getByRole("button", { name: "DOT" })).toBeInTheDocument())
      await user.click(screen.getByRole("button", { name: "DOT" }))
      await waitFor(() => expect(screen.getByText(DOT_COPY)).toBeInTheDocument())
      await vi.advanceTimersByTimeAsync(2_000)
      await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument())
      expect(screen.queryByText("live")).not.toBeInTheDocument()
      expect(screen.getByText(DOT_COPY)).toBeInTheDocument()
      expect(screen.queryByText(TIMING_COPY)).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("knowledge ingest progress", () => {
  test("shows processing progress counts and failed-page status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input)
        if (url === "/api/sites") {
          return jsonOk({
            items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
            widget_origin: "http://widget.localhost:3000",
          })
        }
        if (url === `/api/sites/${SITE_ID}/kb-sources`) {
          return jsonOk({
            items: [
              {
                id: SOURCE_ID,
                site_id: SITE_ID,
                start_url: PAGE_URL,
                mode: "list",
                status: "running",
                stage: "processing",
                error_code: null,
                page_count: 7,
                pages_discovered: 12,
                pages_embedded: 7,
                pages_failed: 2,
                enabled: true,
              },
            ],
          })
        }
        if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
          return jsonOk({
            items: [
              {
                id: PAGE_ID,
                source_id: SOURCE_ID,
                url: PAGE_URL,
                title: PAGE_TITLE,
                enabled: true,
                processing_status: "embedding",
              },
            ],
          })
        }
        return { ok: false, status: 404, json: async () => ({}) }
      }),
    )
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByText("Processing 7 of 12 pages")).toBeInTheDocument())
    const bar = screen.getByRole("progressbar", { name: "Ingestion progress" })
    expect(bar).toHaveAttribute("aria-valuenow", "7")
    expect(bar).toHaveAttribute("aria-valuemax", "12")
    expect(screen.getByText("2 pages failed")).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("Embedding")).toBeInTheDocument())
  })
})

describe("knowledge terminal failures", () => {
  test("keeps terminal failures visible and explains the latest crawl event", async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(createFailedProgressFetch())
    vi.stubGlobal("fetch", fetchMock)
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(
        screen.getByText("Sync failed — live unchanged (FAQ answers did not match)"),
      ).toBeInTheDocument(),
    )
    expect(screen.getByText("1 page failed")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Live answers were left unchanged. Review the failed rule, then retry the crawl.",
      ),
    ).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("Skipped (validation failed)")).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText("Crawl activity")).toBeInTheDocument())
    expect(screen.getByText(/browser renderer crashed · crawl4ai/)).toBeInTheDocument()
    await user.click(await screen.findByRole("button", { name: "Retry page" }))
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/kb-pages/${PAGE_ID}/retry`,
      expect.objectContaining({ method: "POST" }),
    )
  })
})
