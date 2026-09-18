import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import {
  CHUNK_ID,
  CONTACT_BODY,
  DEMO_PAGE_TITLE,
  demoKnowledgeFetch,
  diffRaceFetch,
  FCRA_TITLE,
  knowledgeFetch,
  OTHER_PAGE_TITLE,
  PAGE_ID,
  PAGE_TITLE,
  releaseDiffHold,
  releaseEasyHold,
  resetEasyHold,
  SITE_ID,
  TIMING_BODY,
  twoBrandFetch,
  twoSourceFetch,
  multiPageFetch,
} from "./knowledge-test-fetch"

describe("knowledge demo site", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(demoKnowledgeFetch))
  })

  test("choosing Demo again keeps the Demo page details", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: DEMO_PAGE_TITLE })).toBeInTheDocument(),
    )
    await waitFor(() => expect(screen.getByText(TIMING_BODY)).toBeInTheDocument())
    await user.click(screen.getByLabelText("Site"))
    await user.click(await screen.findByRole("option", { name: "Demo" }))
    expect(screen.getByRole("button", { name: DEMO_PAGE_TITLE })).toBeInTheDocument()
    expect(screen.getByText(TIMING_BODY)).toBeInTheDocument()
    expect(
      screen.queryByText("Add a website or trusted text this site should answer from."),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText("Indexed pages").parentElement?.querySelector(".tabular-nums"),
    ).toHaveTextContent("1")
  })

  test("clicking the Demo page again keeps the retrieved answers", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    const demoPage = await screen.findByRole("button", { name: DEMO_PAGE_TITLE })
    await waitFor(() => expect(screen.getByText(TIMING_BODY)).toBeInTheDocument())
    await user.click(demoPage)
    expect(screen.getByText(TIMING_BODY)).toBeInTheDocument()
    expect(screen.queryByText("Indexed copy")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: DEMO_PAGE_TITLE })).toBeInTheDocument()
  })
})

describe("knowledge console", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("lists the timing page and disable persists enabled false", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: PAGE_TITLE }))
    await user.click(await screen.findByRole("button", { name: "Disable page" }))
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Enable page" })).toBeInTheDocument(),
    )
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
    await user.click(await screen.findByRole("button", { name: PAGE_TITLE }))
    await user.click(await screen.findByRole("button", { name: "Disable page" }))
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Enable page" })).toBeInTheDocument(),
    )
    await user.click(screen.getByRole("button", { name: "Enable page" }))
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

  test("clicking a source card expands its pages and collapses every other source", async () => {
    vi.stubGlobal("fetch", vi.fn(twoSourceFetch))
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: PAGE_TITLE })).toBeInTheDocument(),
    )
    expect(screen.queryByRole("button", { name: OTHER_PAGE_TITLE })).not.toBeInTheDocument()
    const otherCard = screen.getByText("Sample Data Services").closest("[data-slot='collapsible']")
    if (!(otherCard instanceof HTMLElement)) {
      throw new Error("expected the SampleData source card")
    }
    await user.click(within(otherCard).getByText("Ready"))
    expect(screen.getByRole("button", { name: OTHER_PAGE_TITLE })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: PAGE_TITLE })).not.toBeInTheDocument(),
    )
  })
})

describe("knowledge add website", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("add website posts the typed urls", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "Add knowledge" }))
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

  test("add plain text posts one text source", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "Add knowledge" }))
    await user.click(screen.getByRole("button", { name: "Plain text" }))
    await user.type(screen.getByLabelText("Title"), "Collections policy")
    await user.type(
      screen.getByLabelText("Content"),
      "Payment plans are reviewed by the collections team.",
    )
    await user.click(screen.getByRole("button", { name: "Add text" }))

    const posted = vi
      .mocked(fetch)
      .mock.calls.find(
        (call) =>
          String(call[0]) === `/api/sites/${SITE_ID}/kb-sources` &&
          (call[1] as RequestInit)?.method === "POST" &&
          JSON.parse(String((call[1] as RequestInit).body)).kind === "text",
      )
    expect(posted).toBeDefined()
    expect(JSON.parse(String((posted![1] as RequestInit).body))).toEqual({
      kind: "text",
      title: "Collections policy",
      body: "Payment plans are reviewed by the collections team.",
    })
  })

  test("view progress on a first index lists the added units", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "View progress" }))
    await waitFor(() => expect(screen.getByText("Initial index: 1 unit.")).toBeInTheDocument())
    expect(screen.queryByText("No added units.")).not.toBeInTheDocument()
  })

  test("add website shows an inline error for a non-https URL", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "Add knowledge" }))
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

  test("clicking a page shows the retrieved answers the assistant uses", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: PAGE_TITLE })).toBeInTheDocument(),
    )
    await user.click(screen.getByRole("button", { name: PAGE_TITLE }))
    await waitFor(() => expect(screen.getByText("Retrieved answers")).toBeInTheDocument())
    expect(screen.queryByText("Indexed copy")).not.toBeInTheDocument()
    const panel = screen.getByText("Retrieved answers").closest("section")
    if (panel === null) {
      throw new Error("expected retrieved answers panel")
    }
    await waitFor(() => expect(within(panel).getByText(TIMING_BODY)).toBeInTheDocument())
    expect(within(panel).getByText("Section")).toBeInTheDocument()
    expect(within(panel).getByText(/1 of 1 answers/)).toBeInTheDocument()
  })

  test("an administrator can exclude one retrieved answer without removing it", async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: PAGE_TITLE }))
    const include = await screen.findByRole("switch", { name: "Include Turnaround in answers" })
    await user.click(include)
    await waitFor(() => expect(screen.getByText(/0 of 1 answers/)).toBeInTheDocument())
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
      expect(screen.getAllByRole("button", { name: "View progress" })).toHaveLength(2),
    )
    const viewButtons = screen.getAllByRole("button", { name: "View progress" })
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

describe("knowledge general tab", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(multiPageFetch))
  })

  test("opens shared answers on the General tab with the pages they came from", async () => {
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByRole("button", { name: "General" })).toBeInTheDocument())
    expect(screen.getByRole("button", { name: "SampleMail" })).toBeInTheDocument()
    expect(screen.getByText("Contact")).toBeInTheDocument()
    expect(screen.getByText(CONTACT_BODY)).toBeInTheDocument()
    expect(screen.getByText("Also on Home and SampleMail")).toBeInTheDocument()
  })
})
