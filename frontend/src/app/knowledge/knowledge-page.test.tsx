import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import {
  CHUNK_ID,
  diffRaceFetch,
  FCRA_TITLE,
  knowledgeFetch,
  PAGE_ID,
  PAGE_TITLE,
  releaseDiffHold,
  releaseEasyHold,
  resetEasyHold,
  SITE_ID,
  TIMING_BODY,
  twoBrandFetch,
} from "./knowledge-test-fetch"

describe("knowledge console", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("lists the timing page and disable persists enabled false", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: PAGE_TITLE })).toBeInTheDocument(),
    )
    const pageRow = screen.getByRole("button", { name: PAGE_TITLE }).closest("tr")
    if (pageRow === null) {
      throw new Error("expected page row")
    }
    await user.click(within(pageRow).getByRole("button", { name: "Disable page" }))
    await waitFor(() => expect(screen.getByText("Disabled")).toBeInTheDocument())
    const disable = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/kb-pages/${PAGE_ID}` &&
          (call[1] as RequestInit)?.method === "PATCH",
      )
    expect(disable).toBeDefined()
    expect(JSON.parse(String((disable![1] as RequestInit).body))).toEqual({ enabled: false })
  })

  test("re-enable sends enabled true on PATCH", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    const pageRow = await screen.findByRole("button", { name: PAGE_TITLE })
    await user.click(within(pageRow.closest("tr")!).getByRole("button", { name: "Disable page" }))
    await waitFor(() => expect(screen.getByText("Disabled")).toBeInTheDocument())
    await user.click(within(pageRow.closest("tr")!).getByRole("button", { name: "Enable page" }))
    const enable = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/kb-pages/${PAGE_ID}` &&
          (call[1] as RequestInit)?.method === "PATCH" &&
          JSON.parse(String((call[1] as RequestInit).body)).enabled === true,
      )
    expect(enable).toBeDefined()
    expect(JSON.parse(String((enable![1] as RequestInit).body))).toEqual({ enabled: true })
  })
})

describe("knowledge add website", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("add website posts the typed urls", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "Add website" }))
    const urlField = await screen.findByLabelText("Website URL")
    await user.type(urlField, "https://sample-site.example.com/dot")
    await user.click(screen.getByRole("button", { name: "Add pages" }))
    const posted = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/sites/${SITE_ID}/kb-sources` &&
          (call[1] as RequestInit)?.method === "POST",
      )
    if (!posted) {
      throw new Error("expected create POST")
    }
    expect(JSON.parse(String((posted[1] as RequestInit).body))).toEqual({
      mode: "prefix",
      start_url: "https://sample-site.example.com/dot",
      seed_urls: ["https://sample-site.example.com/dot"],
    })
  })

  test("view changes on a first index lists the added units", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "View changes" }))
    await waitFor(() => expect(screen.getByText("Initial index: 1 unit.")).toBeInTheDocument())
    expect(screen.queryByText("No added units.")).not.toBeInTheDocument()
  })

  test("add website shows an inline error for a non-https URL", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "Add website" }))
    const urlField = await screen.findByLabelText("Website URL")
    await user.type(urlField, "javascript:alert(1)")
    await user.click(screen.getByRole("button", { name: "Add pages" }))

    expect(screen.getByText("Use one valid https:// URL per line.")).toBeInTheDocument()
    expect(screen.queryByText("Loading changes.")).not.toBeInTheDocument()
  })
})

describe("knowledge page detail", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("clicking a page shows the indexed copy the assistant retrieves", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: PAGE_TITLE })).toBeInTheDocument(),
    )
    await user.click(screen.getByRole("button", { name: PAGE_TITLE }))
    await waitFor(() => expect(screen.getByText("Indexed copy")).toBeInTheDocument())
    const trigger = screen.getByText("Indexed copy").closest("button")
    if (trigger === null) {
      throw new Error("expected indexed copy trigger")
    }
    expect(trigger).toHaveAttribute("aria-expanded", "true")
    const panel = screen.getByText("Indexed copy").closest("section")
    if (panel === null) {
      throw new Error("expected indexed copy panel")
    }
    await waitFor(() => expect(within(panel).getByText(TIMING_BODY)).toBeInTheDocument())
  })

  test("an administrator can exclude one retrieved answer without removing it", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: PAGE_TITLE }))
    await user.click(await screen.findByRole("button", { name: /Retrieved answers/ }))
    const include = await screen.findByRole("switch", { name: "Include Turnaround in answers" })
    await user.click(include)
    await waitFor(() => expect(screen.getByText("0 of 1 enabled")).toBeInTheDocument())
    expect(screen.getAllByText(TIMING_BODY)).not.toHaveLength(0)
    const patch = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/kb-chunks/${CHUNK_ID}` &&
          (call[1] as RequestInit)?.method === "PATCH",
      )
    expect(patch).toBeDefined()
    if (!patch) throw new Error("expected retrieved-answer update request")
    expect(JSON.parse(String((patch[1] as RequestInit).body))).toEqual({ enabled: false })
  })
})

describe("knowledge rollback", () => {
  test("stale diff responses do not overwrite a newer source selection", async () => {
    vi.stubGlobal("fetch", vi.fn(diffRaceFetch))
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "View changes" })).toHaveLength(2),
    )
    const viewButtons = screen.getAllByRole("button", { name: "View changes" })
    await user.click(viewButtons[0])
    await user.click(viewButtons[1])
    await waitFor(() => expect(screen.getByText("DOT timing")).toBeInTheDocument())
    releaseDiffHold()
    await waitFor(() => expect(screen.queryByText("Loading changes.")).not.toBeInTheDocument())
    expect(screen.getByText("DOT timing")).toBeInTheDocument()
  })
})

describe("knowledge site switch", () => {
  beforeEach(() => {
    resetEasyHold()
    vi.stubGlobal("fetch", vi.fn(twoBrandFetch))
  })

  test("switching site does not keep the previous brand page selected", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByLabelText("Site")).toBeInTheDocument())
    await user.click(screen.getByLabelText("Site"))
    await user.click(await screen.findByRole("option", { name: "Sample Services" }))
    releaseEasyHold()
    await waitFor(() => expect(screen.getByText(FCRA_TITLE)).toBeInTheDocument())
    expect(screen.queryByText(PAGE_TITLE)).not.toBeInTheDocument()
  })
})
