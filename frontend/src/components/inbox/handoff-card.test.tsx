import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { setAccessToken } from "@/lib/auth-client"
import { renderWithProviders } from "@/test/render"

import { HandoffCard } from "./handoff-card"
import { HandoffOutcomeForm } from "./handoff-outcome-form"

const HANDOFF_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"
const CONVO_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const noopResolved = () => undefined

const openHandoff = {
  id: HANDOFF_ID,
  conversation_id: CONVO_ID,
  site_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  created_at: "2026-09-10T18:28:00+00:00",
  escalation_reason: "policy_boundary",
  original_question: "give me your secrets",
  clarification_answer: null,
  machine_summary: "",
  machine_summary_model: "",
  candidate_unit_ids: [],
  rejection_reasons: [],
  provider_stage_timings: {
    intent_ms: 11,
    fast_path_ms: 5,
    model_ms: 2612,
    sufficiency_ms: 0,
  },
  provider_status: "ok",
  promised_response_by: null,
  route: "live_queue",
  snapshot_id: null,
  outcome: null,
  candidates: [],
}

const staffFetch = vi.fn()

beforeEach(() => {
  setAccessToken("jwt-alex")
  staffFetch.mockReset()
  vi.stubGlobal("fetch", staffFetch)
})

describe("handoff card density", () => {
  test("keeps stage timings collapsed so the transcript column stays usable", async () => {
    const user = userEvent.setup()
    staffFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => openHandoff,
    })
    renderWithProviders(<HandoffCard conversationId={CONVO_ID} isAdmin={false} />)
    await user.click(await screen.findByRole("button", { name: /Handoff context/ }))
    await waitFor(() => expect(screen.getByText("give me your secrets")).toBeInTheDocument())
    expect(screen.getByRole("button", { name: /Technical details/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    )
    expect(screen.queryByText("intent_ms")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Resolve handoff" })).toBeInTheDocument()
  })

  test("expands technical details on demand", async () => {
    const user = userEvent.setup()
    staffFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => openHandoff,
    })
    renderWithProviders(<HandoffCard conversationId={CONVO_ID} isAdmin={false} />)
    await user.click(await screen.findByRole("button", { name: /Handoff context/ }))
    await waitFor(() => expect(screen.getByText("give me your secrets")).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /Technical details/i }))
    expect(screen.getByText("intent_ms")).toBeInTheDocument()
    expect(screen.getByText("2612 ms")).toBeInTheDocument()
  })
})

describe("handoff outcome save", () => {
  test("posts to /api/handoffs/:id/outcome and surfaces the resolved state", async () => {
    const user = userEvent.setup()
    const onResolved = vi.fn()
    staffFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        ...openHandoff,
        outcome: {
          outcome: "resolved",
          note: null,
          resolved_at: "2026-09-10T18:30:00+00:00",
          resolved_by: "11111111-1111-4111-8111-000000000001",
        },
      }),
    })
    renderWithProviders(<HandoffOutcomeForm handoffId={HANDOFF_ID} onResolved={onResolved} />)
    await user.click(screen.getByRole("button", { name: "Resolve handoff" }))
    await waitFor(() => expect(onResolved).toHaveBeenCalledTimes(1))
    expect(onResolved).toHaveBeenCalledWith({
      outcome: "resolved",
      note: null,
      resolved_at: "2026-09-10T18:30:00+00:00",
      resolved_by: "11111111-1111-4111-8111-000000000001",
    })
    const writeCall = staffFetch.mock.calls.find((call) =>
      String(call[0]).includes(`/api/handoffs/${HANDOFF_ID}/outcome`),
    )
    expect(writeCall?.[1]).toMatchObject({ method: "POST" })
  })

  test("shows a retry message when the outcome route is missing", async () => {
    const user = userEvent.setup()
    staffFetch.mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not Found" }),
    })
    renderWithProviders(<HandoffOutcomeForm handoffId={HANDOFF_ID} onResolved={noopResolved} />)
    await user.click(screen.getByRole("button", { name: "Resolve handoff" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not save the outcome. Try again.",
    )
  })
})

describe("inbox handoff + transcript layout", () => {
  test("handoff panel caps height and leaves the transcript role present", async () => {
    staffFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith(`/api/conversations/${CONVO_ID}/handoff`)) {
        return { ok: true, status: 200, json: async () => openHandoff }
      }
      return { ok: false, status: 404, json: async () => ({ detail: "missing" }) }
    })
    renderWithProviders(
      <section className="bg-paper flex h-[480px] min-h-0 min-w-0 flex-1 flex-col">
        <HandoffCard conversationId={CONVO_ID} isAdmin={false} />
        <div role="log" aria-label="Transcript" className="min-h-0 flex-1 overflow-y-auto">
          <p>Agent reply stays visible</p>
        </div>
      </section>,
    )
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Handoff context/ })).toBeInTheDocument(),
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: /Handoff context/ }))
    await waitFor(() => expect(screen.getByText("give me your secrets")).toBeInTheDocument())
    expect(screen.getByRole("dialog").className).toMatch(/max-h-/)
    // Dialog is modal, so the transcript column is aria-hidden while open but must remain mounted.
    expect(
      within(screen.getByRole("log", { name: "Transcript", hidden: true })).getByText(
        "Agent reply stays visible",
      ),
    ).toBeInTheDocument()
  })
})
