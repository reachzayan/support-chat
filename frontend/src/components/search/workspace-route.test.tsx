import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, test, vi } from "vitest"

import { SitesConsole } from "@/app/sites/sites-console"
import { SITE } from "@/app/sites/sites-test-fixtures"
import { InboxConsole } from "@/components/inbox/inbox-console"
import { ALEX, CONVO_ID, resetInboxHarness } from "@/components/inbox/inbox-test-harness"
import { renderWithProviders } from "@/test/render"

import { WorkspaceRoute } from "./workspace-route"
const { route } = vi.hoisted(() => ({ route: { query: "site=other", pathname: "/admin/sites" } }))
vi.mock("next/navigation", () => ({
  usePathname: () => route.pathname,
  useSearchParams: () => new URLSearchParams(route.query),
}))
test("same-page result navigation and browser Back reopen the exact site", async () => {
  vi.stubGlobal("fetch", async () =>
    Response.json({
      items: [{ ...SITE, id: "other", name: "Other site" }, SITE],
      widget_origin: "http://widget.localhost:3000",
    }),
  )
  const { rerender } = renderWithProviders(
    <WorkspaceRoute>
      <SitesConsole isAdmin displayName="Alex" />
    </WorkspaceRoute>,
  )
  expect(
    within(await screen.findByRole("dialog", { name: "Manage site" })).getByLabelText("Name"),
  ).toHaveValue("Other site")
  route.query = `site=${SITE.id}`
  rerender(
    <WorkspaceRoute>
      <SitesConsole isAdmin displayName="Alex" />
    </WorkspaceRoute>,
  )
  await waitFor(() =>
    expect(
      within(screen.getByRole("dialog", { name: "Manage site" })).getByLabelText("Name"),
    ).toHaveValue("SampleSite Support"),
  )
  route.query = "site=other"
  rerender(
    <WorkspaceRoute>
      <SitesConsole isAdmin displayName="Alex" />
    </WorkspaceRoute>,
  )
  await waitFor(() =>
    expect(
      within(screen.getByRole("dialog", { name: "Manage site" })).getByLabelText("Name"),
    ).toHaveValue("Other site"),
  )
  vi.unstubAllGlobals()
})

test("clearing an inbox deep link preserves the selected conversation filter", async () => {
  resetInboxHarness()
  route.pathname = "/admin/inbox"
  route.query = `conversation=${CONVO_ID}`
  window.history.replaceState(null, "", `/admin/inbox?${route.query}`)
  const { rerender } = renderWithProviders(
    <WorkspaceRoute>
      <InboxConsole user={ALEX} initialConversationId={CONVO_ID} />
    </WorkspaceRoute>,
  )
  await screen.findByRole("log", { name: "Transcript" })
  await userEvent.setup().click(screen.getByRole("button", { name: "Needs Attention" }))
  route.query = ""
  rerender(
    <WorkspaceRoute>
      <InboxConsole user={ALEX} initialConversationId={null} />
    </WorkspaceRoute>,
  )
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveAttribute(
      "aria-pressed",
      "true",
    ),
  )
})
