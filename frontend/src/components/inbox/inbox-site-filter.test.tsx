import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { InboxConsole } from "./inbox-console"
import {
  ALEX,
  BG_SITE,
  EASY_SITE,
  resetInboxHarness,
  setListSites,
  staffFetch,
} from "./inbox-test-harness"

const SITE_KEY = "supportchat.inbox.site-id"

const inboxPicker = () => screen.getByRole("combobox", { name: /^Inbox\b/ })

const inboxValue = () => {
  const value = inboxPicker().querySelector('[data-slot="select-value"]')
  if (value === null) {
    throw new Error("inbox picker has no selected value")
  }
  return value
}

const chooseInbox = async (user: ReturnType<typeof userEvent.setup>, name: string | RegExp) => {
  await user.click(inboxPicker())
  await user.click(await screen.findByRole("option", { name }))
}

const openNeedsAttention = async () => {
  const user = userEvent.setup()
  const view = renderWithProviders(<InboxConsole user={ALEX} />)
  await user.click(screen.getByRole("button", { name: "Needs Attention" }))
  await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
  return { user, view }
}

describe("inbox site filter", () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetInboxHarness()
  })

  test("All keeps SampleSite and Sample Services rows together", async () => {
    await openNeedsAttention()
    expect(screen.getByText("Ada Lopez")).toBeInTheDocument()
    expect(screen.getByText("Other Visitor")).toBeInTheDocument()
    expect(inboxValue()).toHaveTextContent(/^All 2$/)
  })

  test("SampleSite hides Sample Services rows", async () => {
    const { user } = await openNeedsAttention()
    await chooseInbox(user, /^SampleSite 1$/)
    await waitFor(() => expect(screen.queryByText("Other Visitor")).not.toBeInTheDocument())
    expect(screen.getByText("Ada Lopez")).toBeInTheDocument()
  })

  test("Sample Services hides SampleSite rows", async () => {
    const { user } = await openNeedsAttention()
    await chooseInbox(user, /^Sample Services 1$/)
    await waitFor(() => expect(screen.queryByText("Ada Lopez")).not.toBeInTheDocument())
    expect(screen.getByText("Other Visitor")).toBeInTheDocument()
  })

  test("remembers SampleSite after a remount", async () => {
    const { user, view } = await openNeedsAttention()
    await chooseInbox(user, /^SampleSite 1$/)
    await waitFor(() => expect(screen.queryByText("Other Visitor")).not.toBeInTheDocument())
    expect(window.localStorage.getItem(SITE_KEY)).toBe(EASY_SITE)
    view.unmount()

    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(inboxValue()).toHaveTextContent(/^SampleSite 1$/))
    await user.click(screen.getByRole("button", { name: "Needs Attention" }))
    await waitFor(() => expect(screen.getByText("Ada Lopez")).toBeInTheDocument())
    expect(screen.queryByText("Other Visitor")).not.toBeInTheDocument()
  })

  test("an unknown stored site id falls back to All", async () => {
    window.localStorage.setItem(SITE_KEY, "99999999-9999-4999-8999-999999999999")
    await openNeedsAttention()
    expect(inboxValue()).toHaveTextContent(/^All 2$/)
    expect(screen.getByText("Ada Lopez")).toBeInTheDocument()
    expect(screen.getByText("Other Visitor")).toBeInTheDocument()
  })
})

describe("inbox site chips and queued counts", () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetInboxHarness()
  })

  test("All shows a site chip on each row", async () => {
    await openNeedsAttention()
    const adaRow = screen.getByRole("button", { name: /Ada Lopez/ })
    const otherRow = screen.getByRole("button", { name: /Other Visitor/ })
    expect(within(adaRow).getByText("SampleSite")).toBeInTheDocument()
    expect(within(otherRow).getByText("Sample Services")).toBeInTheDocument()
  })

  test("a single-site filter hides the site chip on rows", async () => {
    const { user } = await openNeedsAttention()
    await chooseInbox(user, /^SampleSite 1$/)
    await waitFor(() => expect(screen.queryByText("Other Visitor")).not.toBeInTheDocument())
    const adaRow = screen.getByRole("button", { name: /Ada Lopez/ })
    await waitFor(() => expect(within(adaRow).queryByText("SampleSite")).not.toBeInTheDocument())
  })

  test("inbox picker is a dropdown with All 2, SampleSite 1, and Sample Services 1", async () => {
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(inboxValue()).toHaveTextContent(/^All 2$/))
    expect(screen.queryByRole("navigation", { name: "Site filter" })).not.toBeInTheDocument()
    await user.click(inboxPicker())
    expect(await screen.findByRole("option", { name: "All 2" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "SampleSite 1" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Sample Services 1" })).toBeInTheDocument()
  })

  test("twenty inboxes appear as options instead of a slider", async () => {
    const manyInboxes = Array.from({ length: 20 }, (_, index) => ({
      id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      name: `Inbox ${index + 1}`,
      queued: 0,
    }))
    setListSites(manyInboxes)
    const user = userEvent.setup()
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(inboxValue()).toHaveTextContent(/^All 0$/))
    await user.click(inboxPicker())
    expect(await screen.findByRole("option", { name: "Inbox 1 0" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Inbox 20 0" })).toBeInTheDocument()
    expect(screen.getAllByRole("option")).toHaveLength(21)
  })

  test("SampleSite scopes Needs Attention to 1 instead of 2", async () => {
    const { user } = await openNeedsAttention()
    expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveTextContent(
      /^Needs Attention 2$/,
    )
    await chooseInbox(user, /^SampleSite 1$/)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Needs Attention" })).toHaveTextContent(
        /^Needs Attention 1$/,
      ),
    )
    expect(inboxValue()).toHaveTextContent(/^SampleSite 1$/)
    await user.click(inboxPicker())
    expect(await screen.findByRole("option", { name: "Sample Services 1" })).toBeInTheDocument()
  })
})

describe("inbox elsewhere queued signal", () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetInboxHarness()
  })

  test("SampleSite shows 1 elsewhere when Sample Services still has Needs Attention", async () => {
    const { user } = await openNeedsAttention()
    await chooseInbox(user, /^SampleSite 1$/)
    await waitFor(() =>
      expect(screen.getByLabelText("1 needs attention in other inboxes")).toBeInTheDocument(),
    )
    expect(inboxValue()).toHaveTextContent(/^SampleSite 1$/)
    expect(inboxPicker()).toHaveAccessibleName(/1 needs attention in other inboxes/)
  })

  test("All does not show an elsewhere badge", async () => {
    await openNeedsAttention()
    expect(inboxValue()).toHaveTextContent(/^All 2$/)
    expect(screen.queryByLabelText(/needs attention in other inboxes/)).not.toBeInTheDocument()
  })

  test("SampleSite hides elsewhere when no other inbox is queued", async () => {
    setListSites([
      { id: EASY_SITE, name: "SampleSite", queued: 1 },
      { id: BG_SITE, name: "Sample Services", queued: 0 },
    ])
    const { user } = await openNeedsAttention()
    await chooseInbox(user, /^SampleSite 1$/)
    await waitFor(() => expect(inboxValue()).toHaveTextContent(/^SampleSite 1$/))
    expect(screen.queryByLabelText(/needs attention in other inboxes/)).not.toBeInTheDocument()
  })

  test("inbox picker trigger uses a solid border hover instead of a wash shadow", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(inboxValue()).toHaveTextContent(/^All 2$/))
    const trigger = inboxPicker()
    expect(trigger.className).toMatch(/hover:border-navy/)
    expect(trigger.className).not.toMatch(/shadow-\[/)
    expect(trigger.className).toMatch(/\bbg-paper\b/)
  })

  test("search and inbox picker share the compact status filter track without stretching", async () => {
    renderWithProviders(<InboxConsole user={ALEX} />)
    await waitFor(() => expect(inboxValue()).toHaveTextContent(/^All 2$/))
    const search = screen.getByRole("searchbox", { name: "Search chats" })
    const trigger = inboxPicker()
    const filters = screen.getByRole("navigation", { name: "Inbox filters" })
    const track = filters.parentElement
    expect(track).not.toBeNull()
    expect(track?.contains(search)).toBe(true)
    expect(track?.contains(trigger)).toBe(true)
    expect(track?.className).toMatch(/\bw-fit\b/)
    expect(track?.className).toMatch(/inline-flex/)
    expect(track?.className).toMatch(/\bself-start\b/)
    expect(search.className.split(/\s+/)).toContain("w-full")
    expect(search.className.split(/\s+/)).toContain("min-w-0")
    expect(trigger.className.split(/\s+/)).toContain("w-full")
    expect(filters.className.split(/\s+/)).toContain("w-fit")
  })
})

describe("inbox list load failure", () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetInboxHarness()
  })

  test("a failed list load shows Inbox could not be loaded instead of Inbox clear", async () => {
    staffFetch.mockImplementation(async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: "unavailable" }),
    }))
    renderWithProviders(<InboxConsole user={ALEX} />)
    expect(await screen.findByRole("alert")).toHaveTextContent("Inbox could not be loaded")
    expect(screen.queryByText("Inbox clear")).not.toBeInTheDocument()
  })

  test("a failed SampleSite load keeps SampleSite selected instead of switching to All", async () => {
    window.localStorage.setItem(SITE_KEY, EASY_SITE)
    staffFetch.mockImplementation(async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: "unavailable" }),
    }))
    renderWithProviders(<InboxConsole user={ALEX} />)
    expect(await screen.findByRole("alert")).toHaveTextContent("Inbox could not be loaded")
    expect(inboxValue()).not.toHaveTextContent(/^All/)
  })
})
