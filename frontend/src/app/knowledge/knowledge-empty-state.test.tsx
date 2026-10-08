import { screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import { jsonOk, SITE_ID, siteRecord } from "./knowledge-test-fetch"

const emptyFetch = async (input: RequestInfo) => {
  const url = String(input)
  if (url.endsWith("/kb-sources")) {
    return jsonOk({ items: [] })
  }
  return jsonOk({
    items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
    widget_origin: "http://widget.localhost:3000",
  })
}

describe("knowledge empty state", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(emptyFetch))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  test("shows one empty state with a single primary action", async () => {
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    expect(await screen.findByRole("heading", { name: "No knowledge sources yet" })).toBeVisible()
    expect(screen.getAllByText(/Add a website or trusted text/)).toHaveLength(1)
    expect(screen.queryByText("Add a source to get started.")).not.toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: "Add knowledge" })).toHaveLength(1)
  })

  test("non-admins get the explanation without an action", async () => {
    renderWithProviders(<KnowledgeConsole isAdmin={false} displayName="Riley Chen" />)
    expect(await screen.findByRole("heading", { name: "No knowledge sources yet" })).toBeVisible()
    expect(screen.queryByRole("button", { name: "Add knowledge" })).not.toBeInTheDocument()
  })
})
