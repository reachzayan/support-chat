import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { toast } from "@/components/ui/toast"
import { renderWithProviders } from "@/test/render"

import { KnowledgeConsole } from "./knowledge-console"
import {
  CHUNK_ID,
  jsonOk,
  knowledgeFetch,
  PAGE_ID,
  PAGE_TITLE,
  TIMING_BODY,
} from "./knowledge-test-fetch"

const EDITED_BODY = "DOT-regulated testing posts the next business day."
const LOCK_KEY = "supportchat:kb-chunk-edit"
const LOCK_EDIT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

const chunkPatchCalls = () =>
  vi
    .mocked(fetch)
    .mock.calls.filter(
      (call) => String(call[0]) === `/api/kb-chunks/${CHUNK_ID}` && call[1]?.method === "PATCH",
    )

const chunkPatchBodies = () =>
  chunkPatchCalls().map(
    (call) =>
      JSON.parse(String(call[1]?.body)) as { enabled?: boolean; body?: string; edit_id?: string },
  )

const bodyPatchCalls = () =>
  chunkPatchCalls().filter((call) => {
    const payload = JSON.parse(String(call[1]?.body)) as { body?: string }
    return payload.body !== undefined
  })

const expectToast = (title: string) =>
  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument()

const noopRelease = () => undefined

const heldBodyPatch = () => {
  let release: (value?: void | PromiseLike<void>) => void = noopRelease
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  const fetchImpl = async (input: RequestInfo, init?: RequestInit) => {
    if (String(input) === `/api/kb-chunks/${CHUNK_ID}` && init?.method === "PATCH") {
      const payload = JSON.parse(String(init.body)) as {
        body?: string
        edit_id?: string
        enabled?: boolean
      }
      if (payload.body !== undefined) {
        await held
        return jsonOk({
          id: CHUNK_ID,
          ordinal: 0,
          kind: "section",
          heading: PAGE_TITLE,
          body: payload.body,
          enabled: payload.enabled ?? true,
          last_body_edit_id: payload.edit_id ?? null,
        })
      }
    }
    return knowledgeFetch(input, init)
  }
  return { release: () => release(), fetchImpl }
}

const openEditor = async () => {
  const user = userEvent.setup()
  renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
  await screen.findByText(TIMING_BODY)
  await user.click(screen.getByRole("button", { name: "Edit Turnaround" }))
  return user
}

const writeLock = () => {
  localStorage.setItem(
    LOCK_KEY,
    JSON.stringify({
      chunkId: CHUNK_ID,
      pageId: PAGE_ID,
      editId: LOCK_EDIT_ID,
      body: EDITED_BODY,
    }),
  )
}

afterEach(() => {
  localStorage.clear()
  toast.close()
})

describe("knowledge answer inline edit", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(knowledgeFetch))
  })

  test("an administrator can open an inline editor on a retrieved answer", async () => {
    await openEditor()
    expect(screen.getByRole("textbox", { name: "Retrieved answer" })).toHaveValue(TIMING_BODY)
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument()
  })

  test("a specialist without admin access cannot edit retrieved answers", async () => {
    renderWithProviders(<KnowledgeConsole isAdmin={false} displayName="Alex Morgan" />)
    await screen.findByText(TIMING_BODY)
    expect(screen.queryByRole("button", { name: "Edit Turnaround" })).not.toBeInTheDocument()
  })

  test("discard restores the original answer and does not save", async () => {
    const user = await openEditor()
    const editor = screen.getByRole("textbox", { name: "Retrieved answer" })
    await user.clear(editor)
    await user.type(editor, EDITED_BODY)
    await user.click(screen.getByRole("button", { name: "Discard" }))
    expect(screen.getByText(TIMING_BODY)).toBeInTheDocument()
    expect(screen.queryByRole("textbox", { name: "Retrieved answer" })).not.toBeInTheDocument()
    expect(chunkPatchBodies().filter((body) => body.body !== undefined)).toHaveLength(0)
  })

  test("losing focus does not save the draft", async () => {
    const user = await openEditor()
    const editor = screen.getByRole("textbox", { name: "Retrieved answer" })
    await user.clear(editor)
    await user.type(editor, EDITED_BODY)
    await user.click(screen.getByRole("heading", { name: "Retrieved answers" }))
    expect(screen.getByRole("textbox", { name: "Retrieved answer" })).toHaveValue(EDITED_BODY)
    expect(chunkPatchBodies().filter((body) => body.body !== undefined)).toHaveLength(0)
  })

  test("save writes the new answer and shows a success toast", async () => {
    const user = await openEditor()
    const editor = screen.getByRole("textbox", { name: "Retrieved answer" })
    await user.clear(editor)
    await user.type(editor, EDITED_BODY)
    await user.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() => expect(screen.getByText(EDITED_BODY)).toBeInTheDocument())
    expect(screen.queryByRole("textbox", { name: "Retrieved answer" })).not.toBeInTheDocument()
    expectToast("Answer saved")
    const saved = bodyPatchCalls()
    expect(saved).toHaveLength(1)
    expect(saved[0]?.[1]?.keepalive).toBe(true)
    const payload = JSON.parse(String(saved[0]?.[1]?.body)) as { body?: string; edit_id?: string }
    expect(payload.body).toBe(EDITED_BODY)
    expect(payload.edit_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    )
  })
})

describe("knowledge answer in-flight save", () => {
  afterEach(() => {
    localStorage.clear()
    toast.close()
  })

  test("a second save is ignored until the first edit finishes", async () => {
    const held = heldBodyPatch()
    vi.stubGlobal("fetch", vi.fn(held.fetchImpl))
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await screen.findByText(TIMING_BODY)
    await user.click(screen.getByRole("button", { name: "Edit Turnaround" }))
    const editor = screen.getByRole("textbox", { name: "Retrieved answer" })
    await user.clear(editor)
    await user.type(editor, EDITED_BODY)
    await user.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() => expectToast("Saving answer"))
    await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeDisabled())
    await user.click(screen.getByRole("button", { name: "Save" }))
    expect(chunkPatchBodies().filter((body) => body.body !== undefined)).toHaveLength(1)
    held.release()
    await waitFor(() => expectToast("Answer saved"))
  })

  test("a failed save shows an error toast and allows another edit afterward", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo, init?: RequestInit) => {
        if (String(input) === `/api/kb-chunks/${CHUNK_ID}` && init?.method === "PATCH") {
          const payload = JSON.parse(String(init.body)) as { body?: string }
          if (payload.body !== undefined) {
            return { ok: false, status: 503, json: async () => ({ detail: "unavailable" }) }
          }
        }
        return knowledgeFetch(input, init)
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await screen.findByText(TIMING_BODY)
    await user.click(screen.getByRole("button", { name: "Edit Turnaround" }))
    const editor = screen.getByRole("textbox", { name: "Retrieved answer" })
    await user.clear(editor)
    await user.type(editor, EDITED_BODY)
    await user.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Answer could not be saved"),
    )
    expect(screen.getByRole("textbox", { name: "Retrieved answer" })).toHaveValue(EDITED_BODY)
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled()
  })

  test("a conflicting save shows a warning and keeps the latest retrieved answer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo, init?: RequestInit) => {
        if (String(input) === `/api/kb-chunks/${CHUNK_ID}` && init?.method === "PATCH") {
          const payload = JSON.parse(String(init.body)) as { body?: string }
          if (payload.body !== undefined) {
            return { ok: false, status: 409, json: async () => ({ detail: "conflict" }) }
          }
        }
        return knowledgeFetch(input, init)
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await screen.findByText(TIMING_BODY)
    await user.click(screen.getByRole("button", { name: "Edit Turnaround" }))
    const editor = screen.getByRole("textbox", { name: "Retrieved answer" })
    await user.clear(editor)
    await user.type(editor, EDITED_BODY)
    await user.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("This page changed during save"),
    )
    expect(screen.getByText(TIMING_BODY)).toBeInTheDocument()
  })
})

describe("knowledge answer save resume", () => {
  afterEach(() => {
    localStorage.clear()
    toast.close()
  })

  test("reloading with an in-flight edit retries the same save and blocks a new edit", async () => {
    const held = heldBodyPatch()
    writeLock()
    vi.stubGlobal("fetch", vi.fn(held.fetchImpl))
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await screen.findByText(TIMING_BODY)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Edit Turnaround" })).toBeDisabled(),
    )
    await waitFor(() => expectToast("Saving answer"))
    const inFlight = bodyPatchCalls()
    expect(inFlight).toHaveLength(1)
    expect(inFlight[0]?.[1]?.keepalive).toBe(true)
    expect(JSON.parse(String(inFlight[0]?.[1]?.body))).toEqual({
      body: EDITED_BODY,
      edit_id: LOCK_EDIT_ID,
    })
    held.release()
    await waitFor(() => expect(screen.getByText(EDITED_BODY)).toBeInTheDocument())
    expectToast("Answer saved")
    expect(screen.getByRole("button", { name: "Edit Turnaround" })).toBeEnabled()
    expect(localStorage.getItem(LOCK_KEY)).toBeNull()
  })

  test("reloading after a save that already landed does not patch again", async () => {
    writeLock()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo, init?: RequestInit) => {
        if (String(input) === `/api/kb-pages/${PAGE_ID}` && init?.method !== "PATCH") {
          return jsonOk({
            id: PAGE_ID,
            source_id: "22222222-2222-4222-8222-222222222222",
            url: "https://sample-site.example.com/faq",
            title: PAGE_TITLE,
            enabled: true,
            chunk_count: 1,
            skip_reason: null,
            content_text: TIMING_BODY,
            chunks: [
              {
                id: CHUNK_ID,
                ordinal: 0,
                kind: "section",
                heading: PAGE_TITLE,
                body: EDITED_BODY,
                enabled: true,
                last_body_edit_id: LOCK_EDIT_ID,
              },
            ],
          })
        }
        return knowledgeFetch(input, init)
      }),
    )
    renderWithProviders(<KnowledgeConsole isAdmin={true} displayName="Riley Chen" />)
    await waitFor(() => expect(screen.getByText(EDITED_BODY)).toBeInTheDocument())
    expect(bodyPatchCalls()).toHaveLength(0)
    expectToast("Answer already saved")
    expect(screen.getByRole("button", { name: "Edit Turnaround" })).toBeEnabled()
    expect(localStorage.getItem(LOCK_KEY)).toBeNull()
  })
})
