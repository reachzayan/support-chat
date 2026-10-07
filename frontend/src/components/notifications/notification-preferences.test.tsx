import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"

import NotificationSettingsPage from "@/app/admin/notifications/page"
import { SelectionContext } from "@/components/search/workspace-route"
import { renderWithProviders } from "@/test/render"

import { NotificationsProvider } from "./notifications-context"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))

const sites = [
  {
    site_id: "easy",
    site_name: "SampleSite",
    scenarios: {
      live: true,
      bot: false,
      needs_attention: true,
      visitor_message: true,
      closed: false,
    },
    push: { enabled: true, scenarios: ["needs_attention", "visitor_message"] },
  },
  {
    site_id: "careers",
    site_name: "Careers",
    scenarios: {
      live: false,
      bot: true,
      needs_attention: false,
      visitor_message: true,
      closed: true,
    },
    push: { enabled: false, scenarios: ["bot"] },
  },
]

const renderPreferences = () =>
  renderWithProviders(
    <NotificationsProvider enabled={false}>
      <NotificationSettingsPage />
    </NotificationsProvider>,
  )

afterEach(() => vi.unstubAllGlobals())

// Oracle: the requested site dropdown must show only the selected site's controls.
test("the site dropdown shows one site's preferences at a time", async () => {
  vi.stubGlobal("fetch", async () => Response.json({ sites }))
  const user = userEvent.setup()
  renderPreferences()

  const selector = await screen.findByRole("combobox", { name: "Website" })
  expect(selector).toHaveTextContent("SampleSite")
  expect(screen.getByRole("switch", { name: "Live chats for SampleSite" })).toBeChecked()
  expect(screen.queryByRole("switch", { name: "Live chats for Careers" })).not.toBeInTheDocument()

  await user.click(selector)
  await user.click(await screen.findByRole("option", { name: "Careers" }))
  expect(selector).toHaveTextContent("Careers")
  expect(screen.getByRole("switch", { name: "Live chats for Careers" })).not.toBeChecked()
  expect(
    screen.queryByRole("switch", { name: "Live chats for SampleSite" }),
  ).not.toBeInTheDocument()
})

// Oracle: saving a site preference stays scoped to that site after selection changes.
test("a save finishing after switching sites is retained when returning", async () => {
  let completeSave!: (response: Response) => void
  const write = new Promise<Response>((resolve) => {
    completeSave = resolve
  })
  let savedPreference: unknown
  vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "PUT") {
      savedPreference = JSON.parse(String(init.body))
      return write
    }
    return Response.json({ sites })
  })
  const user = userEvent.setup()
  renderPreferences()
  const selector = await screen.findByRole("combobox", { name: "Website" })
  await user.click(screen.getByRole("switch", { name: "Visitor replies for SampleSite" }))
  await user.click(selector)
  await user.click(await screen.findByRole("option", { name: "Careers" }))
  await act(async () => {
    completeSave(new Response(null, { status: 204 }))
  })

  expect(savedPreference).toEqual({ site_id: "easy", scenario: "visitor_message", in_app: false })
  expect(screen.getByRole("switch", { name: "Visitor replies for Careers" })).toBeChecked()
  await user.click(selector)
  await user.click(await screen.findByRole("option", { name: "SampleSite" }))
  await waitFor(() =>
    expect(
      screen.getByRole("switch", { name: "Visitor replies for SampleSite" }),
    ).not.toBeChecked(),
  )
})

test("site push toggle preserves its selected types and the site's in-app alerts", async () => {
  const saved: unknown[] = []
  vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "PUT") {
      saved.push(JSON.parse(String(init.body)))
      return new Response(null, { status: 204 })
    }
    return Response.json({ sites })
  })
  const user = userEvent.setup()
  renderPreferences()
  const push = await screen.findByRole("switch", { name: "Push notifications for SampleSite" })
  await user.click(push)
  await waitFor(() => expect(push).not.toBeChecked())
  expect(screen.getByRole("switch", { name: "Needs attention for SampleSite" })).toBeChecked()
  expect(screen.getByRole("combobox", { name: "Push activity for SampleSite" })).toBeDisabled()
  await user.click(push)
  await waitFor(() => expect(push).toBeChecked())
  expect(saved).toEqual([
    { site_id: "easy", enabled: false, scenarios: ["needs_attention", "visitor_message"] },
    { site_id: "easy", enabled: true, scenarios: ["needs_attention", "visitor_message"] },
  ])
})

test("push activity dropdown saves multiple types for the selected site only", async () => {
  let saved: unknown
  vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "PUT") {
      saved = JSON.parse(String(init.body))
      return new Response(null, { status: 204 })
    }
    return Response.json({ sites })
  })
  const user = userEvent.setup()
  renderPreferences()
  const types = await screen.findByRole("combobox", { name: "Push activity for SampleSite" })
  await user.click(types)
  await user.click(await screen.findByRole("option", { name: "Bot conversations" }))
  await waitFor(() =>
    expect(saved).toEqual({
      site_id: "easy",
      enabled: true,
      scenarios: ["needs_attention", "visitor_message", "bot"],
    }),
  )
  await user.keyboard("{Escape}")
  const selector = screen.getByRole("combobox", { name: "Website" })
  await user.click(selector)
  await user.click(await screen.findByRole("option", { name: "Careers" }))
  expect(screen.getByRole("switch", { name: "Push notifications for Careers" })).not.toBeChecked()
  await user.click(selector)
  await user.click(await screen.findByRole("option", { name: "SampleSite" }))
  await user.click(screen.getByRole("combobox", { name: "Push activity for SampleSite" }))
  expect(await screen.findByRole("option", { name: "Bot conversations" })).toHaveAttribute(
    "aria-selected",
    "true",
  )
})

test("a failed push save leaves the previous selection available", async () => {
  vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === "PUT" ? new Response(null, { status: 503 }) : Response.json({ sites }),
  )
  const user = userEvent.setup()
  renderPreferences()
  const push = await screen.findByRole("switch", { name: "Push notifications for SampleSite" })
  await user.click(push)
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not save push")
  expect(push).toBeChecked()
})

const SEARCH_SELECTION = { site: "careers" }
test("search opens notification preferences for the exact website", async () => {
  vi.stubGlobal("fetch", async () => Response.json({ sites }))
  renderWithProviders(
    <SelectionContext.Provider value={SEARCH_SELECTION}>
      <NotificationsProvider enabled={false}>
        <NotificationSettingsPage />
      </NotificationsProvider>
    </SelectionContext.Provider>,
  )
  expect(await screen.findByRole("combobox", { name: "Website" })).toHaveTextContent("Careers")
  expect(screen.getByRole("switch", { name: "Bot conversations for Careers" })).toBeInTheDocument()
  expect(
    screen.queryByRole("switch", { name: "Bot conversations for SampleSite" }),
  ).not.toBeInTheDocument()
})
