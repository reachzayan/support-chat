import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, test, vi } from "vitest"

import { renderWithProviders } from "@/test/render"

import { PushPreference } from "./push-preference"

const serviceWorkerDescriptor = Object.getOwnPropertyDescriptor(navigator, "serviceWorker")
afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
  if (serviceWorkerDescriptor)
    Object.defineProperty(navigator, "serviceWorker", serviceWorkerDescriptor)
  else Reflect.deleteProperty(navigator, "serviceWorker")
})

test.each([
  ["granted", "Allowed"],
  ["denied", "Blocked"],
  ["default", "Not requested"],
])(
  "settings shows browser permission %s before the user tries enabling push",
  async (permission, label) => {
    vi.stubGlobal("Notification", { permission })
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { getRegistration: async () => undefined },
    })
    renderWithProviders(<PushPreference />)
    expect(await screen.findByText(`Browser permission: ${label}`)).toBeInTheDocument()
  },
)

test("revoking permission while settings is open updates its status on returning", async () => {
  const notification = { permission: "granted" }
  vi.stubGlobal("Notification", notification)
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: async () => undefined },
  })
  renderWithProviders(<PushPreference />)
  await screen.findByText("Browser permission: Allowed")
  notification.permission = "denied"
  fireEvent(window, new Event("focus"))
  expect(await screen.findByText("Browser permission: Blocked")).toBeInTheDocument()
})

test("settings identifies a browser without notification support", async () => {
  vi.stubGlobal("Notification", undefined)
  renderWithProviders(<PushPreference />)
  expect(await screen.findByText("Browser permission: Unavailable")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Enable push notifications" })).toBeDisabled()
})

test("enable, test, and turn off persist the current device without browser-only JSON fields", async () => {
  let subscribed = false
  let saved: unknown = null
  let tests = 0
  const endpoint = "https://fcm.googleapis.com/fcm/send/device-a"
  const device = {
    endpoint,
    toJSON: () => ({ endpoint, expirationTime: null, keys: { p256dh: "public", auth: "auth" } }),
    unsubscribe: async () => {
      subscribed = false
      return true
    },
  }
  const registration = {
    active: {
      postMessage: (_message: unknown, ports: MessagePort[]) =>
        ports[0].postMessage({ ok: true }, []),
    },
    getNotifications: async () => [],
    pushManager: {
      getSubscription: async () => (subscribed ? device : null),
      subscribe: async () => {
        subscribed = true
        return device
      },
    },
  }
  const notification = {
    permission: "default",
    requestPermission: async () => {
      notification.permission = "granted"
      return "granted"
    },
  }
  vi.stubGlobal("Notification", notification)
  vi.stubGlobal("PushManager", function PushManager() {
    return null
  })
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: async () => registration, register: async () => registration },
  })
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).endsWith("/config"))
      return Response.json({ configured: true, public_key: "AQID" })
    if (init?.method === "DELETE") {
      saved = null
      return new Response(null, { status: 204 })
    }
    if (String(input).endsWith("/test")) {
      tests += 1
      return new Response(null, { status: 202 })
    }
    saved = JSON.parse(String(init?.body))
    return Response.json({ id: "22222222-2222-4222-8222-000000000002" })
  })
  const user = userEvent.setup()
  renderWithProviders(<PushPreference />)
  expect(screen.getByText("Browser permission: Not requested")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Enable push notifications" }))
  expect(await screen.findByRole("button", { name: "Turn off push" })).toBeEnabled()
  expect(screen.getByText("Browser permission: Allowed")).toBeInTheDocument()
  expect(saved).toEqual({ endpoint, keys: { p256dh: "public", auth: "auth" }, silent: false })
  await user.click(screen.getByRole("button", { name: "Send test notification" }))
  expect(await screen.findByRole("status")).toHaveTextContent("Test notification queued")
  expect(tests).toBe(1)
  await user.click(screen.getByRole("button", { name: "Turn off push" }))
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Enable push notifications" })).toBeEnabled(),
  )
  expect(subscribed).toBe(false)
  expect(saved).toBeNull()
})

test("blocked permission leaves push off and gives a recovery instruction", async () => {
  vi.stubGlobal("Notification", { permission: "denied" })
  vi.stubGlobal("PushManager", function PushManager() {
    return null
  })
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: async () => undefined },
  })
  const user = userEvent.setup()
  renderWithProviders(<PushPreference />)
  await user.click(screen.getByRole("button", { name: "Enable push notifications" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Allow them in your browser settings")
  expect(screen.queryByRole("button", { name: "Turn off push" })).not.toBeInTheDocument()
})
