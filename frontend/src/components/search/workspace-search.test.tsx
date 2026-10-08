import { act, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { staffRequest } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import type { SearchResults } from "./search-destinations"
import { WorkspaceSearch } from "./workspace-search"
const { push } = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/inbox",
  useRouter: () => ({ push }),
}))
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual("@/lib/auth-client")),
  staffRequest: vi.fn(),
}))
const item = (id: string, title: string, href: string, target: "inbox" | "sites" = "inbox") => ({
  id,
  title,
  href,
  screen: target,
  description: "SampleSite · New visitor message",
  kind: "conversation",
})
const empty: SearchResults = { current: [], navigation: [], other: [] }
const response = (results: SearchResults) => new Response(JSON.stringify(results), { status: 200 })
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(staffRequest).mockResolvedValue(response(empty))
})
afterEach(() => vi.unstubAllGlobals())
const open = async (isAdmin = true) => {
  renderWithProviders(<WorkspaceSearch isAdmin={isAdmin} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole("combobox", { name: "Search workspace records" }))
  return { user, input: screen.getByRole("combobox", { name: "Search workspace records" }) }
}

test("the toolbar input stays the only input when its results dropdown opens", async () => {
  renderWithProviders(<WorkspaceSearch isAdmin />)
  const user = userEvent.setup()
  const input = screen.getByRole("combobox", { name: "Search workspace records" })
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
  await user.click(input)
  const results = await screen.findByRole("listbox", { name: "Workspace results" })
  expect(screen.getAllByRole("combobox")).toHaveLength(1)
  expect(results).not.toContainElement(input)
  expect(input).toHaveFocus()
  expect(input).toHaveAttribute("aria-expanded", "true")
  expect(input).toHaveAttribute("aria-controls", results.id)
  await user.keyboard("{Escape}")
  await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
  expect(input).toHaveFocus()
  expect(input).toHaveAttribute("aria-expanded", "false")
})

test("the shortcut opens and focuses the toolbar input before it has ever been clicked", async () => {
  renderWithProviders(<WorkspaceSearch isAdmin />)
  const input = screen.getByRole("combobox", { name: "Search workspace records" })
  fireEvent.keyDown(document, { key: "k", metaKey: true })
  expect(await screen.findByRole("listbox", { name: "Workspace results" })).toBeInTheDocument()
  await waitFor(() => expect(input).toHaveFocus())
  await userEvent.setup().keyboard("{Escape}")
  await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
  expect(input).toHaveFocus()
  fireEvent.keyDown(document, { key: "k", ctrlKey: true })
  expect(await screen.findByRole("listbox", { name: "Workspace results" })).toBeInTheDocument()
  expect(input).toHaveFocus()
})

test("navigation rows show each destination once without a repeated generic description", async () => {
  await open()
  expect(screen.getByRole("option", { name: "Inbox" })).toHaveTextContent(/^Inbox$/)
  expect(screen.getByRole("option", { name: "Sites" })).toHaveTextContent(/^Sites$/)
  expect(screen.getByRole("option", { name: "Knowledge base" })).toHaveTextContent(
    /^Knowledge base$/,
  )
  expect(screen.queryByText("Open workspace view")).not.toBeInTheDocument()
})

test("groups current records first, then navigation and other matches; Enter opens exact chat", async () => {
  vi.mocked(staffRequest).mockResolvedValue(
    response({
      current: [item("one", "Ada Archer", "/admin/inbox?conversation=one")],
      navigation: [
        item("nav:site", "SampleSite · Site settings", "/admin/sites?site=easy", "sites"),
      ],
      other: [item("site:easy", "SampleSite", "/admin/sites?site=easy", "sites")],
    }),
  )
  const { user, input } = await open()
  await user.type(input, "Ada")
  await screen.findByRole("option", { name: /Ada Archer/ })
  expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
    expect.stringContaining("Ada Archer"),
    expect.stringContaining("SampleSite · Site settings"),
    expect.stringContaining("SampleSite"),
  ])
  expect(screen.getByText("This screen · Inbox")).toBeInTheDocument()
  expect(screen.getByText("Other matches")).toBeInTheDocument()
  await user.keyboard("{Enter}")
  expect(push).toHaveBeenCalledWith("/admin/inbox?conversation=one")
})

test("arrow keys select site destination, pointer opens it too", async () => {
  vi.mocked(staffRequest).mockImplementation(async () =>
    response({
      ...empty,
      navigation: [
        item("site1", "SampleSite · Site settings", "/admin/sites?site=easy", "sites"),
        item("site2", "Other · Site settings", "/admin/sites?site=other", "sites"),
      ],
    }),
  )
  const { user, input } = await open()
  await user.type(input, "site")
  await screen.findByRole("option", { name: /SampleSite · Site settings/ })
  await user.keyboard("{ArrowDown}{Enter}")
  expect(push).toHaveBeenCalledWith("/admin/sites?site=other")
  await user.click(screen.getByRole("combobox", { name: "Search workspace records" }))
  await user.type(screen.getByRole("combobox"), "site")
  await user.click(await screen.findByRole("option", { name: /SampleSite · Site settings/ }))
  expect(push).toHaveBeenLastCalledWith("/admin/sites?site=easy")
})

test("stale responses cannot replace a new query; superseded requests abort", async () => {
  let finish: ((r: Response) => void) | undefined
  vi.mocked(staffRequest)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    .mockResolvedValue(
      response({
        ...empty,
        current: [item("new", "Latest chat", "/admin/inbox?conversation=new")],
      }),
    )
  const { user, input } = await open()
  await user.type(input, "old")
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(1))
  const signal = vi.mocked(staffRequest).mock.calls[0][1]?.signal
  await user.clear(input)
  await user.type(input, "new")
  expect(signal?.aborted).toBe(true)
  await screen.findByRole("option", { name: /Latest chat/ })
  await act(async () => {
    finish?.(
      response({
        ...empty,
        current: [item("old", "Outdated chat", "/admin/inbox?conversation=old")],
      }),
    )
  })
  expect(screen.queryByText("Outdated chat")).not.toBeInTheDocument()
})

test("navigation works on error, retry recovers, staff cannot see admin destinations", async () => {
  vi.mocked(staffRequest)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValue(response(empty))
  const { user, input } = await open(false)
  expect(screen.queryByRole("option", { name: /Logs/ })).not.toBeInTheDocument()
  await user.type(input, "sites")
  expect(await screen.findByRole("alert")).toHaveTextContent("Navigation still works")
  expect(screen.getByRole("option", { name: /Sites/ })).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Retry" }))
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument())
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2))
})

test("clear restores destinations; short queries do not request records; literal punctuation is safe", async () => {
  const { user, input } = await open()
  await user.type(input, "x")
  expect(staffRequest).not.toHaveBeenCalled()
  await user.click(screen.getByRole("button", { name: "Clear search" }))
  expect(input).toHaveValue("")
  expect(screen.getByRole("option", { name: "Inbox" })).toBeInTheDocument()
  expect(input).toHaveFocus()
  fireEvent.change(input, { target: { value: "[<script>%_" } })
  await screen.findByText(/No matches across/)
  expect(JSON.parse(String(vi.mocked(staffRequest).mock.calls.at(-1)?.[1]?.body)).query).toBe(
    "[<script>%_",
  )
})

test("input composition cannot send half-written queries or select a destination", async () => {
  const { user, input } = await open()
  fireEvent.compositionStart(input)
  fireEvent.change(input, { target: { value: "東京" } })
  await new Promise((resolve) => setTimeout(resolve, 250))
  expect(staffRequest).not.toHaveBeenCalled()
  fireEvent.keyDown(input, { key: "Enter", isComposing: true })
  expect(push).not.toHaveBeenCalled()
  fireEvent.compositionEnd(input)
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(1))
  await user.keyboard("{Escape}")
})

test("invalid server destinations fail safely and retain trusted navigation", async () => {
  vi.mocked(staffRequest).mockResolvedValue(
    response({
      ...empty,
      navigation: [item("bad", "Untrusted", "https://external.example/", "sites")],
    }),
  )
  const { user, input } = await open()
  await user.type(input, "sites")
  expect(await screen.findByRole("alert")).toHaveTextContent("Navigation still works")
  expect(screen.queryByRole("option", { name: "Untrusted" })).not.toBeInTheDocument()
  expect(screen.getByRole("option", { name: "Sites" })).toHaveAttribute("href", "/admin/sites")
})

test.each([320, 390, 768])(
  "at %i px search supports touch selection and an explicit close button",
  async (width) => {
    vi.stubGlobal("innerWidth", width)
    const { user } = await open()
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus())
    await user.click(screen.getByRole("option", { name: "Notification settings" }))
    expect(push).toHaveBeenCalledWith("/admin/notifications")
    await user.click(screen.getByRole("combobox", { name: "Search workspace records" }))
    await user.click(screen.getByRole("button", { name: "Close search" }))
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
    vi.unstubAllGlobals()
  },
)

test("modifier-click retains native links for opening results in another tab", async () => {
  await open()
  fireEvent.click(screen.getByRole("option", { name: "Sites" }), { ctrlKey: true })
  expect(push).not.toHaveBeenCalled()
  expect(screen.getByRole("option", { name: "Sites" })).toHaveAttribute("href", "/admin/sites")
})

test("search opens without a modal or context strip, and outside controls remain usable", async () => {
  const outsideAction = vi.fn()
  renderWithProviders(
    <>
      <WorkspaceSearch isAdmin />
      <button onClick={outsideAction}>Workspace action</button>
    </>,
  )
  const user = userEvent.setup()
  const trigger = screen.getByRole("combobox", { name: "Search workspace records" })
  await user.click(trigger)
  const popup = await screen.findByRole("listbox", { name: "Workspace results" })
  expect(popup).not.toHaveAttribute("aria-modal", "true")
  expect(screen.queryByText(/Searching in/)).not.toBeInTheDocument()
  expect(screen.getByRole("combobox")).toHaveFocus()
  await user.click(screen.getByRole("button", { name: "Workspace action" }))
  expect(outsideAction).toHaveBeenCalledTimes(1)
  await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
  await user.click(trigger)
  await user.keyboard("{Escape}")
  await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
  expect(trigger).toHaveFocus()
})

test("tabbing out closes results and leaves focus on the next workspace control", async () => {
  renderWithProviders(
    <>
      <WorkspaceSearch isAdmin />
      <button>Workspace action</button>
    </>,
  )
  const user = userEvent.setup()
  await user.click(screen.getByRole("combobox", { name: "Search workspace records" }))
  await screen.findByRole("listbox", { name: "Workspace results" })
  await user.tab()
  expect(screen.getByRole("button", { name: "Close search" })).toHaveFocus()
  await user.tab()
  expect(screen.getByRole("button", { name: "Workspace action" })).toHaveFocus()
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
})

test("Escape from a search control closes results and returns focus to the toolbar input", async () => {
  const { user, input } = await open()
  await user.tab()
  expect(screen.getByRole("button", { name: "Close search" })).toHaveFocus()
  await user.keyboard("{Escape}")
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument()
  expect(input).toHaveFocus()
})
