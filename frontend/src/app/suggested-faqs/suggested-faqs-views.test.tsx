import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { SuggestedFaqsConsole } from "./suggested-faqs-console"

const EASY_SITE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
const ENROLL_GAP = "11111111-1111-4111-8111-111111111111"
const DISMISSED_GAP = "22222222-2222-4222-8222-222222222222"
const ANSWERED_GAP = "33333333-3333-4333-8333-333333333333"
const CANNED_ID = "44444444-4444-4444-8444-444444444444"
const ENROLL = "How do I enroll a driver?"
const REPORT = "Where is my report?"
const PRICING = "How much does it cost?"

const gap = (id: string, question: string, overrides: Record<string, unknown> = {}) => ({
  id,
  site_id: EASY_SITE,
  question,
  conversations: 5,
  last_seen_at: "2026-09-30T15:00:00Z",
  examples: [] as string[],
  spiking: false,
  note: null,
  status: "open",
  resolved_at: null,
  ...overrides,
})

const response = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

const queue = (items: unknown[]) => ({
  items,
  min_conversations: 5,
  window_days: 14,
  spike_conversations: 3,
  spike_hours: 24,
})

type Similar = { canned: unknown; knowledge: unknown }

const stubFetch = (open: unknown[], similar: Similar = { canned: null, knowledge: null }) => {
  setAccessToken("staff-token")
  const routes: Record<string, unknown> = {
    "/api/knowledge-gaps": queue(open),
    "/api/knowledge-gaps?status=dismissed": queue([
      gap(DISMISSED_GAP, REPORT, {
        status: "dismissed",
        resolved_at: "2026-09-29T10:00:00Z",
        note: "Add a report status page.",
      }),
    ]),
    "/api/knowledge-gaps?status=answered": queue([
      gap(ANSWERED_GAP, PRICING, { status: "canned", resolved_at: "2026-09-28T10:00:00Z" }),
    ]),
    "/api/sites": { items: [{ id: EASY_SITE, name: "SampleSite" }] },
    [`/api/knowledge-gaps/${ENROLL_GAP}/replies`]: { items: [] },
    [`/api/knowledge-gaps/${ENROLL_GAP}/similar`]: similar,
  }
  const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === "POST" || init?.method === "PATCH") return response(null, 204)
    return url in routes ? response(routes[url]) : response({ detail: "missing" }, 404)
  })
  vi.stubGlobal("fetch", fetchStub)
  return fetchStub
}

const sent = (fetchStub: ReturnType<typeof stubFetch>, suffix: string, method: string) =>
  fetchStub.mock.calls.find(
    ([url, init]) => String(url).endsWith(suffix) && init?.method === method,
  )

describe("suggested FAQs views", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("marks a question that is spiking right now", async () => {
    stubFetch([gap(ENROLL_GAP, ENROLL, { conversations: 3, spiking: true })])
    renderWithProviders(<SuggestedFaqsConsole />)

    const card = (await screen.findByRole("heading", { name: ENROLL })).closest("article")
    expect(card).not.toBeNull()
    expect(within(card as HTMLElement).getByText("Spiking")).toHaveAttribute(
      "title",
      "3 or more different chats in the last 24 hours",
    )
  })

  test("lists dismissed questions with their note and reopens one", async () => {
    const user = userEvent.setup()
    const fetchStub = stubFetch([gap(ENROLL_GAP, ENROLL)])
    renderWithProviders(<SuggestedFaqsConsole />)
    await screen.findByText(ENROLL)

    await user.click(screen.getByRole("tab", { name: "Dismissed" }))

    expect(await screen.findByText(REPORT)).toBeInTheDocument()
    expect(screen.queryByText(ENROLL)).not.toBeInTheDocument()
    expect(screen.getByText("Add a report status page.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: `Answer: ${REPORT}` })).toBeNull()

    await user.click(screen.getByRole("button", { name: `Reopen: ${REPORT}` }))

    await waitFor(() => expect(screen.queryByText(REPORT)).not.toBeInTheDocument())
    expect(sent(fetchStub, `/api/knowledge-gaps/${DISMISSED_GAP}/reopen`, "POST")).toBeDefined()
  })

  test("moves between the tabs with the arrow keys, as the tab role promises", async () => {
    const user = userEvent.setup()
    stubFetch([gap(ENROLL_GAP, ENROLL)])
    renderWithProviders(<SuggestedFaqsConsole />)
    await screen.findByText(ENROLL)

    screen.getByRole("tab", { name: "Open" }).focus()
    await user.keyboard("{ArrowRight}")

    const answered = screen.getByRole("tab", { name: "Answered" })
    expect(answered).toHaveAttribute("aria-selected", "true")
    expect(answered).toHaveFocus()
    expect(screen.getByRole("tab", { name: "Open" })).toHaveAttribute("tabindex", "-1")

    await user.keyboard("{ArrowLeft}{ArrowLeft}")
    expect(screen.getByRole("tab", { name: "Dismissed" })).toHaveFocus()
    await user.keyboard("{Home}")
    expect(screen.getByRole("tab", { name: "Open" })).toHaveFocus()
  })

  test("lists answered questions and how they were answered", async () => {
    const user = userEvent.setup()
    stubFetch([gap(ENROLL_GAP, ENROLL)])
    renderWithProviders(<SuggestedFaqsConsole />)
    await screen.findByText(ENROLL)

    await user.click(screen.getByRole("tab", { name: "Answered" }))

    expect(await screen.findByText(PRICING)).toBeInTheDocument()
    expect(screen.getByText("Saved as a quick reply")).toBeInTheDocument()
  })

  test("saves a note for the website team and shows it on the card", async () => {
    const user = userEvent.setup()
    const fetchStub = stubFetch([gap(ENROLL_GAP, ENROLL)])
    renderWithProviders(<SuggestedFaqsConsole />)

    await user.click(await screen.findByRole("button", { name: `Add note: ${ENROLL}` }))
    await user.type(screen.getByLabelText("Note for the website team"), "Needs a Get started page.")
    await user.click(screen.getByRole("button", { name: "Save note" }))

    expect(await screen.findByText("Needs a Get started page.")).toBeInTheDocument()
    const patch = sent(fetchStub, `/api/knowledge-gaps/${ENROLL_GAP}`, "PATCH")
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ note: "Needs a Get started page." })
    expect(screen.getByRole("button", { name: `Edit note: ${ENROLL}` })).toBeInTheDocument()
  })
})

describe("suggested FAQs: already close to an existing entry", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("offers to edit a close canned reply and a close knowledge page instead of adding a twin", async () => {
    const user = userEvent.setup()
    stubFetch([gap(ENROLL_GAP, ENROLL)], {
      canned: {
        id: CANNED_ID,
        site_id: EASY_SITE,
        shortcut: "enrollment_process",
        excerpt: "Enroll drivers from the portal.",
        enabled: true,
        bot_eligible: true,
        similarity: 0.9,
      },
      knowledge: {
        title: "Recruiter steps after enrollment",
        heading: "Recruiter steps",
        url: "https://sample-site.example.com/recruiters",
        similarity: 0.8,
      },
    })
    renderWithProviders(<SuggestedFaqsConsole />)

    await user.click(await screen.findByRole("button", { name: `Answer: ${ENROLL}` }))
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })

    expect(await within(dialog).findByText("Already close to this")).toBeInTheDocument()
    expect(within(dialog).getByText("Enroll drivers from the portal.")).toBeInTheDocument()
    expect(
      within(dialog).getByRole("link", { name: "Edit #enrollment_process instead" }),
    ).toHaveAttribute("href", `/admin/canned-responses?scope=${EASY_SITE}&q=enrollment_process`)
    expect(within(dialog).getByText("Recruiter steps after enrollment")).toBeInTheDocument()
    expect(within(dialog).getByRole("link", { name: "Open the knowledge base" })).toHaveAttribute(
      "href",
      "/admin/knowledge",
    )
  })

  test("says nothing when no existing entry is close", async () => {
    const user = userEvent.setup()
    stubFetch([gap(ENROLL_GAP, ENROLL)])
    renderWithProviders(<SuggestedFaqsConsole />)

    await user.click(await screen.findByRole("button", { name: `Answer: ${ENROLL}` }))
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })

    expect(within(dialog).queryByText("Already close to this")).toBeNull()
  })
})
