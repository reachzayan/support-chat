import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { LogsConsole } from "./logs-console"

const LOG_ROW = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  created_at: "2026-09-11T17:30:00Z",
  level: "error",
  source: "backend",
  logger_name: "kb.pipeline",
  event: "ingest_page_failed",
  message: "Fetch timed out for knowledge page",
  detail: { error_class: "TimeoutError", url_host: "sample-site.example.com" },
}

describe("logs console", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.startsWith("/api/logs/dump")) {
          return {
            ok: true,
            status: 200,
            headers: new Headers({ "content-type": "text/plain; charset=utf-8" }),
            text: async () =>
              "2026-09-11T17:30:00Z ERROR source=backend event=ingest_page_failed message=Fetch timed out\n",
          }
        }
        if (url.startsWith("/api/logs")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ items: [LOG_ROW] }),
          }
        }
        return { ok: false, status: 404, json: async () => ({}) }
      }),
    )
  })

  test("renders elaborative log rows in a table and dumps last 7 days", async () => {
    const createObjectURL = vi.fn(() => "blob:logs-dump")
    const revokeObjectURL = vi.fn()
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    })

    renderWithProviders(<LogsConsole isAdmin={true} displayName="Alex Morgan" />)

    const table = await screen.findByRole("table", { name: "Application logs" })
    expect(within(table).getByText("ingest_page_failed")).toBeInTheDocument()
    expect(within(table).getByText("Fetch timed out for knowledge page")).toBeInTheDocument()
    expect(within(table).getByText("error")).toBeInTheDocument()
    expect(within(table).getByText("backend")).toBeInTheDocument()
    expect(within(table).getByText(/2026-09-11/)).toBeInTheDocument()
    expect(within(table).getByText(/TimeoutError/)).toBeInTheDocument()
    expect(table.closest(".overflow-x-scroll")).not.toBeNull()
    expect(table.closest(".overflow-x-auto")).toBeNull()

    await userEvent.setup().click(screen.getByRole("button", { name: "Dump last 7 days" }))

    await waitFor(() => expect(createObjectURL).toHaveBeenCalled())
    const fetchMock = vi.mocked(fetch)
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/api/logs/dump"))).toBe(
      true,
    )
  })
})
