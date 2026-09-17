import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import {
  createIngestQueuedFetch,
  createFailedProgressFetch,
  createReingestSameCountFetch,
  createSelectedPagePollFetch,
  DOT_COPY,
  REINGEST_COPY,
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

const sourceListCalls = (fetchMock: ReturnType<typeof vi.fn>) =>
  fetchMock.mock.calls.filter(
    (call) => String(call[0]) === `/api/sites/${SITE_ID}/kb-sources` && call[1]?.method !== "POST",
  ).length

const showTab = () => {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => "visible",
  })
  document.dispatchEvent(new Event("visibilitychange"))
}

describe("knowledge ingest queued", () => {
  test("queued ingest does not keep requesting sources while the tab stays open", async () => {
    const { fetchFn } = createIngestQueuedFetch()
    const fetchMock = vi.fn(fetchFn)
    vi.stubGlobal("fetch", fetchMock)
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
      await waitFor(() => expect(screen.getByText("Queued")).toBeInTheDocument())
      const requestsWhileQueued = sourceListCalls(fetchMock)
      expect(requestsWhileQueued).toBe(1)
      await vi.advanceTimersByTimeAsync(6_000)
      expect(sourceListCalls(fetchMock)).toBe(1)
      expect(screen.getByText("Queued")).toBeInTheDocument()
      expect(screen.queryByText(PAGE_TITLE)).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  test("returning to the tab lists the page that finished ingesting", async () => {
    const { fetchFn, markIngested } = createIngestQueuedFetch()
    vi.stubGlobal("fetch", vi.fn(fetchFn))
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByText("Queued")).toBeInTheDocument())
    expect(screen.queryByText(PAGE_TITLE)).not.toBeInTheDocument()
    markIngested()
    showTab()
    await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument())
    await waitFor(() =>
      expect(screen.getByRole("button", { name: PAGE_TITLE })).toBeInTheDocument(),
    )
    const indexedLabel = screen.getByText("Indexed pages")
    expect(indexedLabel.parentElement?.querySelector(".tabular-nums")).toHaveTextContent("1")
  })

  test("returning to the tab shows the reingested copy without a full reload", async () => {
    const { fetchFn, markReingested } = createReingestSameCountFetch()
    vi.stubGlobal("fetch", vi.fn(fetchFn))
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByText(TIMING_COPY)).toBeInTheDocument())
    markReingested()
    showTab()
    await waitFor(() => expect(screen.getByText(REINGEST_COPY)).toBeInTheDocument())
    expect(screen.queryByText(TIMING_COPY)).not.toBeInTheDocument()
  })
})

describe("knowledge ingest selection", () => {
  test("returning to the tab after ingest keeps the selected page", async () => {
    vi.stubGlobal("fetch", vi.fn(createSelectedPagePollFetch()))
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByRole("button", { name: "DOT" })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: "DOT" }))
    await waitFor(() => expect(screen.getByText(DOT_COPY)).toBeInTheDocument())
    showTab()
    await waitFor(() => expect(screen.getByText("Ready")).toBeInTheDocument())
    expect(screen.queryByText("live")).not.toBeInTheDocument()
    expect(screen.getByText(DOT_COPY)).toBeInTheDocument()
    expect(screen.queryByText(TIMING_COPY)).not.toBeInTheDocument()
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
                chunk_count: 0,
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
    await user.click(await screen.findByRole("button", { name: PAGE_TITLE }))
    await waitFor(() => expect(screen.getByText("Failed: validation failed")).toBeInTheDocument())
    expect(screen.queryByText("Processing history")).not.toBeInTheDocument()
    await user.click(await screen.findByRole("button", { name: "View progress" }))
    await waitFor(() => expect(screen.getByText("Processing history")).toBeInTheDocument())
    expect(screen.getByText("The browser could not open this page.")).toBeInTheDocument()
    expect(screen.queryByText(/browser renderer crashed/)).not.toBeInTheDocument()
    expect(screen.queryByText(/crawl4ai/)).not.toBeInTheDocument()
    await user.keyboard("{Escape}")
    await user.click(await screen.findByRole("button", { name: "Retry page" }))
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/kb-pages/${PAGE_ID}/retry`,
      expect.objectContaining({ method: "POST" }),
    )
  })
})
