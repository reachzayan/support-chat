import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"

import { BlockedConsole } from "@/app/blocked/blocked-console"
import { CannedResponsesConsole } from "@/app/canned-responses/canned-responses-console"
import { DataConsole } from "@/app/data/data-console"
import { KnowledgeConsole } from "@/app/knowledge/knowledge-console"
import { demoKnowledgeFetch, BG_SITE } from "@/app/knowledge/knowledge-test-fetch"
import { LogsConsole } from "@/app/logs/logs-console"
import { SitesConsole } from "@/app/sites/sites-console"
import { SITE } from "@/app/sites/sites-test-fixtures"
import { renderWithProviders } from "@/test/render"

import { SelectionContext } from "./workspace-route"

const SITE_TARGET = { site: SITE.id }
const KNOWLEDGE_TARGET = { site: BG_SITE }
const RESPONSE_TARGET = { response: "reply2" }
const DATA_TARGET = { conversation: "older-chat" }
const LOG_TARGET = { log: "log2" }
const BLOCK_TARGET = { block: "block2" }
const ok = (body: unknown) => Response.json(body)
afterEach(() => {
  vi.unstubAllGlobals()
  window.history.replaceState(null, "", "/admin/inbox")
})

test("site destination opens the named site's settings, not the first site; closing stays closed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      ok({
        items: [{ ...SITE, id: "other", name: "Other site" }, SITE],
        widget_origin: "http://widget.localhost:3000",
      }),
    ),
  )
  renderWithProviders(
    <SelectionContext.Provider value={SITE_TARGET}>
      <SitesConsole isAdmin displayName="Alex" />
    </SelectionContext.Provider>,
  )
  const dialog = await screen.findByRole("dialog", { name: "Manage site" })
  expect(within(dialog).getByLabelText("Name")).toHaveValue("SampleSite Support")
  await userEvent.setup().keyboard("{Escape}")
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
})

test("knowledge destination selects the requested website before loading sources", async () => {
  const fetchStub = vi.fn(demoKnowledgeFetch)
  vi.stubGlobal("fetch", fetchStub)
  renderWithProviders(
    <SelectionContext.Provider value={KNOWLEDGE_TARGET}>
      <KnowledgeConsole isAdmin displayName="Alex" />
    </SelectionContext.Provider>,
  )
  await waitFor(() =>
    expect(fetchStub).toHaveBeenCalledWith(`/api/sites/${BG_SITE}/kb-sources`, expect.anything()),
  )
  expect(screen.getByRole("combobox", { name: "Site" })).toHaveTextContent("SampleSite")
  expect(fetchStub.mock.calls.some(([url]) => String(url).includes("/api/sites/11111111"))).toBe(
    false,
  )
})

test("a response result opens its edit dialog even when the record is disabled", async () => {
  const replies = [
    {
      id: "reply1",
      site_id: null,
      shortcut: "first",
      body: "First answer",
      enabled: true,
      aliases: [],
      bot_eligible: true,
      created_at: "2026-10-07T12:00:00Z",
      updated_at: "2026-10-07T12:00:00Z",
    },
    {
      id: "reply2",
      site_id: null,
      shortcut: "payroll",
      body: "Payroll details",
      enabled: false,
      aliases: [],
      bot_eligible: true,
      created_at: "2026-10-07T12:00:00Z",
      updated_at: "2026-10-07T12:00:00Z",
    },
  ]
  vi.stubGlobal("fetch", async (url: RequestInfo | URL) =>
    ok({ items: String(url).includes("library") ? replies : [] }),
  )
  renderWithProviders(
    <SelectionContext.Provider value={RESPONSE_TARGET}>
      <CannedResponsesConsole />
    </SelectionContext.Provider>,
  )
  const dialog = await screen.findByRole("dialog")
  expect(within(dialog).getByDisplayValue("payroll")).toHaveValue("payroll")
  expect(within(dialog).getByDisplayValue("Payroll details")).toHaveValue("Payroll details")
})

test("Data opens a submission that was not loaded in its first page", async () => {
  vi.stubGlobal("fetch", async (url: RequestInfo | URL) => {
    const path = String(url)
    if (path.includes("submissions?")) return ok({ items: [], has_more: false })
    if (path.endsWith("/submissions/older-chat"))
      return ok({
        id: "older-chat",
        state: "closed",
        site_name: "SampleSite",
        visitor: { name: "Older visitor" },
      })
    return ok({
      id: "older-chat",
      state: "closed",
      site_name: "SampleSite",
      messages: [],
      visitor: {},
    })
  })
  renderWithProviders(
    <SelectionContext.Provider value={DATA_TARGET}>
      <DataConsole />
    </SelectionContext.Provider>,
  )
  expect(await screen.findByRole("dialog", { name: "Older visitor" })).toBeInTheDocument()
})

test("Logs fetches the exact result instead of depending on its recent 500 rows", async () => {
  const fetchStub = vi.fn(async () =>
    ok({
      id: "log2",
      event: "payroll_failed",
      message: "Payroll failed",
      level: "error",
      source: "backend",
      created_at: "2026-10-07T12:00:00Z",
      detail: null,
    }),
  )
  vi.stubGlobal("fetch", fetchStub)
  renderWithProviders(
    <SelectionContext.Provider value={LOG_TARGET}>
      <LogsConsole isAdmin displayName="Alex" />
    </SelectionContext.Provider>,
  )
  expect(await screen.findByText("payroll_failed")).toBeInTheDocument()
  expect(fetchStub).toHaveBeenCalledWith("/api/logs/log2", expect.anything())
})

test("Blocked focuses the selected identifier while preserving its unblock action", async () => {
  vi.stubGlobal("fetch", async () =>
    ok({
      items: [
        { id: "block1", site_name: "Other", email: "other@example.com", created_at: "2026-10-07" },
        {
          id: "block2",
          site_name: "SampleSite",
          email: "payroll@example.com",
          created_at: "2026-10-07",
        },
      ],
    }),
  )
  renderWithProviders(
    <SelectionContext.Provider value={BLOCK_TARGET}>
      <BlockedConsole />
    </SelectionContext.Provider>,
  )
  expect(await screen.findByText("payroll@example.com")).toBeInTheDocument()
  expect(screen.queryByText("other@example.com")).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Unblock visitor on SampleSite" })).toBeInTheDocument()
})
