import { fireEvent, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { SitesConsole } from "./sites-console"
import { mockListFetch, SITE, SNIPPET } from "./sites-test-fixtures"

describe("sites table", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
  })

  test("renders a compact table without the full snippet textarea", async () => {
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    const table = await screen.findByRole("table", { name: "Sites" })
    expect(within(table).getByText("SampleSite Support")).toBeInTheDocument()
    expect(within(table).getByText("samplesite")).toBeInTheDocument()
    expect(within(table).getByText("1 origin")).toBeInTheDocument()
    expect(within(table).getByText("Bot on")).toBeInTheDocument()
    expect(within(table).getByText("Human on")).toBeInTheDocument()
    expect(screen.queryByLabelText("Embed snippet")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Add new website" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Manage" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Copy snippet" })).toBeInTheDocument()
    expect(within(table).getByText("Site on")).toBeInTheDocument()
    expect(table.closest(".overflow-x-auto")).not.toBeNull()
    expect(table.style.minWidth).not.toBe("")
  })
})

describe("sites copy snippet", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
  })

  test("copies the fixture snippet and shows Copied on the button for one second", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    })
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await screen.findByRole("table", { name: "Sites" })
    const copyButton = screen.getByRole("button", { name: "Copy snippet" })
    fireEvent.click(copyButton)
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(SNIPPET))
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument())
    expect(SNIPPET.includes("YOUR_KEY")).toBe(false)
    expect(SNIPPET.includes("bootstrap_token")).toBe(false)
    expect(SNIPPET.includes("access_token")).toBe(false)
    await waitFor(
      () => expect(screen.getByRole("button", { name: "Copy snippet" })).toBeInTheDocument(),
      { timeout: 2000 },
    )
  })
})

describe("sites column resize", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
  })

  test("column resize only starts after pointer down, not hover", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem")
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await screen.findByRole("table", { name: "Sites" })
    const handle = screen.getByRole("button", { name: "Resize Name column" })
    fireEvent.pointerMove(handle, { clientX: 400, buttons: 0 })
    expect(setItem).not.toHaveBeenCalled()

    fireEvent.pointerDown(handle, { button: 0, clientX: 200 })
    window.dispatchEvent(
      new PointerEvent("pointermove", { clientX: 320, buttons: 1, bubbles: true }),
    )
    window.dispatchEvent(new PointerEvent("pointerup", { clientX: 320, bubbles: true }))
    await waitFor(() =>
      expect(setItem).toHaveBeenCalledWith(
        expect.stringContaining("column-widths"),
        expect.any(String),
      ),
    )
    setItem.mockRestore()
  })
})

describe("sites manage modal", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
  })

  test("manage modal shows the full snippet without a frame-ancestors env warning", async () => {
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await screen.findByRole("table", { name: "Sites" })
    await user.click(screen.getByRole("button", { name: "Manage" }))

    const dialog = await screen.findByRole("dialog", { name: "Manage site" })
    const snippet = within(dialog).getByLabelText("Embed snippet")
    expect(snippet).toHaveValue(SNIPPET)
    expect(
      within(dialog).queryByText("This origin is missing from the widget frame-ancestors header."),
    ).not.toBeInTheDocument()
    expect(within(dialog).getByDisplayValue("https://missing.example")).toBeInTheDocument()
  })
})

describe("sites bot routing", () => {
  test("human switch is not toggleable when the bot is off", async () => {
    let patchBody: Record<string, unknown> | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        if (
          typeof input === "string" &&
          input.startsWith("/api/sites/") &&
          init?.method === "PATCH"
        ) {
          patchBody = JSON.parse(String(init.body)) as Record<string, unknown>
          return {
            ok: true,
            status: 200,
            json: async () => ({ ...SITE, bot_enabled: false, human_enabled: false }),
          }
        }
        return mockListFetch()
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)
    await user.click(await screen.findByRole("button", { name: "Manage" }))
    const dialog = await screen.findByRole("dialog", { name: "Manage site" })
    await waitFor(() => expect(within(dialog).getByRole("switch", { name: "Human" })).toBeEnabled())
    await user.click(within(dialog).getByRole("switch", { name: "AI bot" }))
    await waitFor(() => expect(patchBody).toEqual({ bot_enabled: false, human_enabled: false }))
    await waitFor(() =>
      expect(within(dialog).getByRole("switch", { name: "Human" })).toBeDisabled(),
    )
    expect(within(dialog).getByRole("switch", { name: "Human" })).toHaveAttribute(
      "aria-disabled",
      "true",
    )
  })
})

const CREATED_SITE = {
  ...SITE,
  id: "22222222-2222-4222-8222-222222222222",
  key: "sample-services-a1b2",
  name: "Sample Services",
  public_key: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  origins: ["https://sample-services.example.com"],
  snippet: SNIPPET.replaceAll("samplesite", "sample-services-a1b2"),
  origins_missing_from_frame_ancestors: false,
  website_url: "https://sample-services.example.com",
  widget_installed: false,
  widget_checked_at: "2026-09-16T15:00:00Z",
}

const emptySitesFetch = () => ({
  ok: true,
  status: 200,
  json: async () => ({
    items: [],
    frame_ancestors: ["http://localhost:3000"],
    widget_origin: "http://widget.localhost:3000",
  }),
})

const fillAddWebsiteForm = async (
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
) => {
  await user.type(within(dialog).getByLabelText("Name"), "Sample Services")
  await user.type(
    within(dialog).getByLabelText("Website URL"),
    "https://sample-services.example.com/careers",
  )
  await user.type(
    within(dialog).getByLabelText("Privacy URL"),
    "https://sample-services.example.com/privacy",
  )
  await user.type(
    within(dialog).getByLabelText("Greeting"),
    "Talk to a specialist about screening.",
  )
}

describe("sites add website form", () => {
  test("add website fields appear in install order", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await user.click(await screen.findByRole("button", { name: "Add new website" }))
    const dialog = await screen.findByRole("dialog", { name: "Add new website" })
    const labels = ["Name", "Website URL", "Privacy URL", "Approved origins", "Greeting"].map(
      (label) => within(dialog).getByText(label),
    )
    for (let index = 0; index < labels.length - 1; index += 1) {
      expect(labels[index].compareDocumentPosition(labels[index + 1])).toBe(
        Node.DOCUMENT_POSITION_FOLLOWING,
      )
    }
  })

  test("website URL locks its origin into approved origins and that lock cannot be removed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await user.click(await screen.findByRole("button", { name: "Add new website" }))
    const dialog = await screen.findByRole("dialog", { name: "Add new website" })
    await user.type(
      within(dialog).getByLabelText("Website URL"),
      "https://sample-services.example.com/careers",
    )

    const origins = within(dialog).getByText("Approved origins").closest("[data-slot=field]")
    expect(origins).not.toBeNull()
    expect(
      within(origins as HTMLElement).getByText("https://sample-services.example.com"),
    ).toBeInTheDocument()
    expect(
      within(origins as HTMLElement).queryByRole("button", { name: /remove/i }),
    ).not.toBeInTheDocument()
  })

  test("add website shows inline errors when required fields are empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await screen.findByText("SampleSite Support")
    await user.click(screen.getByRole("button", { name: "Add new website" }))
    const dialog = await screen.findByRole("dialog", { name: "Add new website" })
    await user.click(within(dialog).getByRole("button", { name: "Create website" }))

    expect(within(dialog).getByText("Name is required.")).toBeInTheDocument()
    expect(within(dialog).getByText("Privacy URL is required.")).toBeInTheDocument()
    expect(within(dialog).getByText("Website URL is required.")).toBeInTheDocument()
    expect(within(dialog).queryByText("Add at least one approved origin.")).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText("Name")).toHaveAttribute("aria-invalid", "true")
  })
})

describe("sites add website create flow", () => {
  test("creating a website keeps the dialog open with the snippet, install steps, and an install check", async () => {
    const created = { ...CREATED_SITE }
    let postBody: Record<string, unknown> | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        if (typeof input === "string" && input === "/api/sites" && init?.method === "POST") {
          postBody = JSON.parse(String(init.body)) as Record<string, unknown>
          return { ok: true, status: 201, json: async () => created }
        }
        return emptySitesFetch()
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await screen.findByText("No sites configured")
    await user.click(screen.getByRole("button", { name: "Add new website" }))
    const form = await screen.findByRole("dialog", { name: "Add new website" })
    expect(within(form).queryByLabelText("Site key")).not.toBeInTheDocument()
    await fillAddWebsiteForm(user, form)
    await user.click(within(form).getByRole("button", { name: "Create website" }))

    const dialog = await screen.findByRole("dialog", { name: "Install the widget" })
    expect(postBody).toEqual({
      name: "Sample Services",
      greeting: "Talk to a specialist about screening.",
      privacy_url: "https://sample-services.example.com/privacy",
      origins: ["https://sample-services.example.com"],
      website_url: "https://sample-services.example.com/careers",
      contact_info: [],
    })
    expect(postBody).not.toHaveProperty("key")
    expect(postBody).not.toHaveProperty("public_key")
    expect(within(dialog).getByLabelText("Embed snippet")).toHaveValue(created.snippet)
    expect(
      within(dialog).getByText("Paste the snippet before the closing body tag."),
    ).toBeInTheDocument()
    expect(within(dialog).getByLabelText("Widget install status")).toHaveTextContent(
      "Not installed",
    )
    expect(within(dialog).getByRole("button", { name: "Copy snippet" })).toBeInTheDocument()

    await user.click(within(dialog).getByRole("button", { name: "Done" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())

    const table = await screen.findByRole("table", { name: "Sites" })
    expect(within(table).getByText("Sample Services")).toBeInTheDocument()
    expect(within(table).getByText("sample-services-a1b2")).toBeInTheDocument()
  })
})

describe("sites add website install check", () => {
  test("install panel refresh rechecks the new site and shows Installed", async () => {
    const created = { ...CREATED_SITE }
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        if (typeof input === "string" && input === "/api/sites" && init?.method === "POST") {
          return { ok: true, status: 201, json: async () => created }
        }
        if (
          typeof input === "string" &&
          input === `/api/sites/${created.id}/check-install` &&
          init?.method === "POST"
        ) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              ...created,
              widget_installed: true,
              widget_checked_at: "2026-09-16T15:05:00Z",
            }),
          }
        }
        return emptySitesFetch()
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await user.click(await screen.findByRole("button", { name: "Add new website" }))
    const form = await screen.findByRole("dialog", { name: "Add new website" })
    await fillAddWebsiteForm(user, form)
    await user.click(within(form).getByRole("button", { name: "Create website" }))

    const dialog = await screen.findByRole("dialog", { name: "Install the widget" })
    await user.click(
      within(dialog).getByRole("button", {
        name: "Recheck install status for Sample Services",
      }),
    )
    await waitFor(() =>
      expect(within(dialog).getByLabelText("Widget install status")).toHaveTextContent("Installed"),
    )
  })
})

// oxlint-disable-next-line max-lines-per-function
describe("sites contact info", () => {
  test("add website sends parsed contact info lines", async () => {
    const created = {
      ...SITE,
      id: "33333333-3333-4333-8333-333333333333",
      key: "sample-services-a1b2",
      name: "Sample Services",
      website_url: "https://sample-services.example.com/careers",
      contact_info: ["555-123-4567", "support@sample-services.example.com"],
    }
    let postBody: Record<string, unknown> | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        if (typeof input === "string" && input === "/api/sites" && init?.method === "POST") {
          postBody = JSON.parse(String(init.body)) as Record<string, unknown>
          return { ok: true, status: 201, json: async () => created }
        }
        return mockListFetch()
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await user.click(await screen.findByRole("button", { name: "Add new website" }))
    const form = await screen.findByRole("dialog", { name: "Add new website" })
    await user.type(within(form).getByLabelText("Name"), "Sample Services")
    await user.type(
      within(form).getByLabelText("Website URL"),
      "https://sample-services.example.com/careers",
    )
    await user.type(
      within(form).getByLabelText("Privacy URL"),
      "https://sample-services.example.com/privacy",
    )
    await user.type(
      within(form).getByLabelText("Contact info"),
      "555-123-4567\nsupport@sample-services.example.com",
    )
    await user.click(within(form).getByRole("button", { name: "Create website" }))

    await screen.findByRole("dialog", { name: "Install the widget" })
    expect(postBody?.contact_info).toEqual(["555-123-4567", "support@sample-services.example.com"])
  })

  test("manage site pre-fills contact info and saves the edited lines", async () => {
    const siteWithContact = { ...SITE, contact_info: ["555-123-4567"] }
    let patchBody: Record<string, unknown> | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        if (
          typeof input === "string" &&
          input.startsWith("/api/sites/") &&
          init?.method === "PATCH"
        ) {
          patchBody = JSON.parse(String(init.body)) as Record<string, unknown>
          return {
            ok: true,
            status: 200,
            json: async () => ({ ...siteWithContact, contact_info: ["support@sample-site.example.com"] }),
          }
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [siteWithContact],
            frame_ancestors: ["http://localhost:3000"],
            widget_origin: "http://widget.localhost:3000",
          }),
        }
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await user.click(await screen.findByRole("button", { name: "Manage" }))
    const dialog = await screen.findByRole("dialog", { name: "Manage site" })
    expect(within(dialog).getByLabelText("Contact info")).toHaveValue("555-123-4567")

    await user.clear(within(dialog).getByLabelText("Contact info"))
    await user.type(within(dialog).getByLabelText("Contact info"), "support@sample-site.example.com")
    await user.click(within(dialog).getByRole("button", { name: "Save" }))

    await waitFor(() => expect(patchBody?.contact_info).toEqual(["support@sample-site.example.com"]))
  })
})

describe("sites leave guard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockListFetch()))
  })

  test("closing manage with unsaved changes asks before leaving", async () => {
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)

    await user.click(await screen.findByRole("button", { name: "Manage" }))
    const dialog = await screen.findByRole("dialog", { name: "Manage site" })
    await user.clear(within(dialog).getByLabelText("Name"))
    await user.type(within(dialog).getByLabelText("Name"), "Renamed brand")
    await user.click(within(dialog).getByRole("button", { name: "Close" }))

    const leave = await screen.findByRole("dialog", { name: "Unsaved changes" })
    expect(
      within(leave).getByText("Do you want to leave? Your changes are not saved."),
    ).toBeInTheDocument()
    await user.click(within(leave).getByRole("button", { name: "Stay" }))
    expect(screen.getByRole("dialog", { name: "Manage site" })).toBeInTheDocument()
    expect(within(dialog).getByLabelText("Name")).toHaveValue("Renamed brand")

    await user.click(within(dialog).getByRole("button", { name: "Close" }))
    const leaveAgain = await screen.findByRole("dialog", { name: "Unsaved changes" })
    await user.click(within(leaveAgain).getByRole("button", { name: "Leave" }))
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Manage site" })).not.toBeInTheDocument(),
    )
  })
})

describe("sites delete", () => {
  test("admin can delete a site from the confirm modal and staff cannot", async () => {
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      if (
        typeof input === "string" &&
        input === `/api/sites/${SITE.id}` &&
        init?.method === "DELETE"
      ) {
        return { ok: true, status: 204, json: async () => ({}) }
      }
      return mockListFetch()
    })
    vi.stubGlobal("fetch", fetchMock)

    const { unmount } = renderWithProviders(
      <SitesConsole isAdmin={false} displayName="Alex Rivera" />,
    )
    await screen.findByRole("table", { name: "Sites" })
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Add new website" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Manage" })).toBeInTheDocument()
    unmount()

    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)
    await screen.findByRole("table", { name: "Sites" })
    await user.click(screen.getByRole("button", { name: "Manage" }))
    const manage = await screen.findByRole("dialog", { name: "Manage site" })
    await user.click(within(manage).getByRole("button", { name: "Delete" }))
    const confirm = await screen.findByRole("dialog", { name: "Delete site" })
    await user.click(within(confirm).getByRole("button", { name: "Delete site" }))
    await waitFor(() => expect(screen.getByText("No sites configured")).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/sites/${SITE.id}`,
      expect.objectContaining({ method: "DELETE" }),
    )
  })
})

describe("sites disable", () => {
  test("manage can disable the site so the widget will not load", async () => {
    let patchBody: Record<string, unknown> | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        if (
          typeof input === "string" &&
          input.startsWith("/api/sites/") &&
          init?.method === "PATCH"
        ) {
          patchBody = JSON.parse(String(init.body)) as Record<string, unknown>
          return {
            ok: true,
            status: 200,
            json: async () => ({ ...SITE, enabled: false }),
          }
        }
        return mockListFetch()
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SitesConsole isAdmin={true} displayName="Riley Chen" />)
    await screen.findByRole("table", { name: "Sites" })
    await user.click(screen.getByRole("button", { name: "Manage" }))
    const dialog = await screen.findByRole("dialog", { name: "Manage site" })
    await user.click(within(dialog).getByRole("switch", { name: "Site" }))
    await waitFor(() => expect(patchBody).toEqual({ enabled: false }))
    await waitFor(() => expect(screen.getByText("Site off")).toBeInTheDocument())
  })
})
