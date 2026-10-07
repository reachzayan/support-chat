import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { PushPreference } from "./push-preference"

const descriptor = Object.getOwnPropertyDescriptor(navigator, "serviceWorker")
afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
  if (descriptor) Object.defineProperty(navigator, "serviceWorker", descriptor)
  else Reflect.deleteProperty(navigator, "serviceWorker")
})

test("the rendered preview follows the selected activity and sends that example to the device", async () => {
  let sent: unknown
  const endpoint = "https://fcm.googleapis.com/fcm/send/device-a"
  const registration = {
    active: {
      postMessage: (_message: unknown, ports: MessagePort[]) =>
        ports[0].postMessage({ ok: true }, []),
    },
    pushManager: { getSubscription: async () => ({ endpoint, toJSON: () => ({ keys: {} }) }) },
  }
  vi.stubGlobal("Notification", { permission: "granted" })
  vi.stubGlobal("PushManager", function PushManager() {
    return null
  })
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: async () => registration },
  })
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes("/preview"))
      return Response.json(
        url.includes("scenario=bot")
          ? {
              title: "Preview: SampleSite · New bot conversation",
              body: "Example chat #A1B2C3 · Portal support\nA visitor started an assistant conversation.",
              action_label: "Open inbox",
            }
          : {
              title: "Preview: SampleSite · Needs attention",
              body: "A visitor requested specialist help.",
              action_label: "Open inbox",
            },
      )
    if (url.endsWith("/test")) {
      sent = JSON.parse(String(init?.body))
      return new Response(null, { status: 202 })
    }
    return Response.json({ id: "22222222-2222-4222-8222-000000000002" })
  })
  const user = userEvent.setup()
  renderWithProviders(<PushPreference siteId="easy" />)
  expect(await screen.findByText("Preview: SampleSite · Needs attention")).toBeInTheDocument()
  await user.click(screen.getByRole("combobox", { name: "Preview activity" }))
  await user.click(await screen.findByRole("option", { name: "Bot conversations" }))
  expect(await screen.findByText("Preview: SampleSite · New bot conversation")).toBeInTheDocument()
  expect(screen.getByText(/Example chat #A1B2C3/)).toBeInTheDocument()
  await user.click(await screen.findByRole("button", { name: "Send test notification" }))
  await waitFor(() => expect(sent).toEqual({ endpoint, site_id: "easy", scenario: "bot" }))
  expect(screen.getByRole("status")).toHaveTextContent("Test notification queued")
})

test("a failed preview provides a retry that restores the example", async () => {
  let failed = true
  vi.stubGlobal("fetch", async () =>
    failed
      ? new Response(null, { status: 503 })
      : Response.json({
          title: "Preview: Careers · Needs attention",
          body: "A visitor requested specialist help.",
          action_label: "Open inbox",
        }),
  )
  const user = userEvent.setup()
  renderWithProviders(<PushPreference siteId="careers" />)
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the preview")
  failed = false
  await user.click(screen.getByRole("button", { name: "Retry preview" }))
  expect(await screen.findByText("Preview: Careers · Needs attention")).toBeInTheDocument()
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
})

test("a late response for the previous website cannot replace the current preview", async () => {
  let finish!: (response: Response) => void
  const old = new Promise<Response>((resolve) => {
    finish = resolve
  })
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) =>
    String(input).includes("site_id=easy")
      ? old
      : Response.json({
          title: "Preview: Careers · Needs attention",
          body: "Current website example",
          action_label: "Open inbox",
        }),
  )
  const view = renderWithProviders(<PushPreference siteId="easy" />)
  await screen.findByText("Loading preview…")
  view.rerender(<PushPreference siteId="careers" />)
  await screen.findByText("Preview: Careers · Needs attention")
  await act(async () =>
    finish(
      Response.json({
        title: "Preview: SampleSite · Needs attention",
        body: "Previous website example",
        action_label: "Open inbox",
      }),
    ),
  )
  await waitFor(() => expect(screen.getByText("Current website example")).toBeInTheDocument())
  expect(screen.queryByText("Previous website example")).not.toBeInTheDocument()
})
