import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { SuggestedFaqsConsole } from "./suggested-faqs-console"

const EASY_SITE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
const BG_SITE = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
const ENROLL_GAP = "11111111-1111-4111-8111-111111111111"
const REPORT_GAP = "22222222-2222-4222-8222-222222222222"
const ENROLL = "How do I enroll a driver?"
const REPORT = "Where is my report?"
const SPECIALIST_ANSWER = "Enroll drivers from the portal under Drivers."
const TAKEN_SHORTCUT = "A response with this shortcut already exists in this scope."

const enrollGap = {
  id: ENROLL_GAP,
  site_id: EASY_SITE,
  question: ENROLL,
  conversations: 7,
  last_seen_at: "2026-09-30T15:00:00Z",
  examples: ["Enrolling a new employee", "how to enroll staff"],
}
const reportGap = {
  id: REPORT_GAP,
  site_id: BG_SITE,
  question: REPORT,
  conversations: 5,
  last_seen_at: "2026-09-28T15:00:00Z",
  examples: [],
}

const response = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

const queue = (items: unknown[]) => ({ items, min_conversations: 5, window_days: 14 })

const getRoutes = (items: unknown[]): Record<string, unknown> => ({
  "/api/knowledge-gaps": queue(items),
  [`/api/knowledge-gaps?site_id=${EASY_SITE}`]: queue([enrollGap]),
  "/api/sites": {
    items: [
      { id: EASY_SITE, name: "SampleSite" },
      { id: BG_SITE, name: "Sample Services" },
    ],
  },
  [`/api/knowledge-gaps/${ENROLL_GAP}/replies`]: { items: [SPECIALIST_ANSWER] },
})

// A POST to /answer succeeds unless the test says the server refused it.
const stubFetch = (items: unknown[], refusal?: { status: number; detail: string }) => {
  setAccessToken("staff-token")
  const routes = getRoutes(items)
  const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === "POST") {
      return refusal && url.endsWith("/answer")
        ? response({ detail: refusal.detail }, refusal.status)
        : response(null, 204)
    }
    return url in routes ? response(routes[url]) : response({ detail: "missing" }, 404)
  })
  vi.stubGlobal("fetch", fetchStub)
  return fetchStub
}

const postedTo = (fetchStub: ReturnType<typeof stubFetch>, suffix: string) =>
  fetchStub.mock.calls.find(
    ([url, init]) => String(url).endsWith(suffix) && init?.method === "POST",
  )

describe("suggested FAQs queue", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("opens the FAQ explanation from its title and returns to the queue", async () => {
    stubFetch([enrollGap])
    renderWithProviders(<SuggestedFaqsConsole />)
    await screen.findByText(ENROLL)
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "How Suggested FAQs work" }))
    const dialog = screen.getByRole("dialog", { name: "How Suggested FAQs work" })
    expect(
      within(dialog).getByRole("heading", { name: "How Suggested FAQs work" }),
    ).toBeInTheDocument()
    await user.keyboard("{Escape}")
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(screen.getByText(ENROLL)).toBeInTheDocument()
  })

  test("ranks repeated questions with their chat counts, other phrasings and website", async () => {
    stubFetch([enrollGap, reportGap])
    renderWithProviders(<SuggestedFaqsConsole />)

    const headings = await screen.findAllByRole("heading", { level: 2 })

    expect(headings.map((heading) => heading.textContent)).toEqual([ENROLL, REPORT])
    expect(screen.getByText("Asked in 7 chats in the last 14 days")).toBeInTheDocument()
    expect(screen.getByText("Asked in 5 chats in the last 14 days")).toBeInTheDocument()
    expect(screen.getByText("Enrolling a new employee")).toBeInTheDocument()
    expect(screen.getByText("how to enroll staff")).toBeInTheDocument()
    expect(screen.getAllByText("SampleSite")).not.toHaveLength(0)
    expect(screen.getAllByText("Sample Services")).not.toHaveLength(0)
  })

  test("explains the rule when no question has repeated enough", async () => {
    stubFetch([])
    renderWithProviders(<SuggestedFaqsConsole />)

    expect(await screen.findByText("No repeated questions yet")).toBeInTheDocument()
    expect(
      screen.getByText(
        "A question appears here after the assistant could not answer it in 5 different chats within 14 days.",
      ),
    ).toBeInTheDocument()
  })

  test("dismissing removes only that question", async () => {
    const user = userEvent.setup()
    const fetchStub = stubFetch([enrollGap, reportGap])
    renderWithProviders(<SuggestedFaqsConsole />)

    await user.click(await screen.findByRole("button", { name: `Dismiss: ${ENROLL}` }))

    await waitFor(() => expect(screen.queryByText(ENROLL)).not.toBeInTheDocument())
    expect(screen.getByText(REPORT)).toBeInTheDocument()
    expect(postedTo(fetchStub, `/api/knowledge-gaps/${ENROLL_GAP}/dismiss`)).toBeDefined()
  })

  test("choosing a website asks the server for that website only", async () => {
    const user = userEvent.setup()
    stubFetch([enrollGap, reportGap])
    renderWithProviders(<SuggestedFaqsConsole />)
    await screen.findByText(REPORT)

    await user.click(screen.getByLabelText("Website"))
    await user.click(await screen.findByRole("option", { name: "SampleSite" }))

    await waitFor(() => expect(screen.queryByText(REPORT)).not.toBeInTheDocument())
    expect(screen.getByText(ENROLL)).toBeInTheDocument()
  })
})

describe("suggested FAQs answering", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  test("saves a specialist's wording as a quick reply and clears the question", async () => {
    const user = userEvent.setup()
    const fetchStub = stubFetch([enrollGap, reportGap])
    renderWithProviders(<SuggestedFaqsConsole />)

    await user.click(await screen.findByRole("button", { name: `Answer: ${ENROLL}` }))
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })
    expect(within(dialog).getByLabelText("Shortcut")).toHaveValue("enroll_driver")
    await user.click(await within(dialog).findByRole("button", { name: /^Use as draft/ }))
    expect(within(dialog).getByLabelText("Answer")).toHaveValue(SPECIALIST_ANSWER)
    await user.click(within(dialog).getByRole("button", { name: "Save answer" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(screen.queryByText(ENROLL)).not.toBeInTheDocument()
    expect(screen.getByText(REPORT)).toBeInTheDocument()
    const call = postedTo(fetchStub, `/api/knowledge-gaps/${ENROLL_GAP}/answer`)
    expect(call).toBeDefined()
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      kind: "canned",
      shortcut: "enroll_driver",
      body: SPECIALIST_ANSWER,
    })
  })

  test("a taken shortcut keeps the dialog open with the server's message", async () => {
    const user = userEvent.setup()
    stubFetch([enrollGap], { status: 409, detail: TAKEN_SHORTCUT })
    renderWithProviders(<SuggestedFaqsConsole />)

    await user.click(await screen.findByRole("button", { name: `Answer: ${ENROLL}` }))
    const dialog = await screen.findByRole("dialog", { name: "Answer this question" })
    await user.type(within(dialog).getByLabelText("Answer"), "Use the portal.")
    await user.click(within(dialog).getByRole("button", { name: "Save answer" }))

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(TAKEN_SHORTCUT)
    expect(screen.getByRole("dialog", { name: "Answer this question" })).toBeInTheDocument()
    expect(screen.getAllByText(ENROLL).length).toBeGreaterThan(0)
  })
})
