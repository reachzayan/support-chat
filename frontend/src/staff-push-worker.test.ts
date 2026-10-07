import { readFileSync } from "node:fs"
import vm from "node:vm"

import { expect, test } from "vitest"

const CHAT = "11111111-1111-4111-8111-000000000001"
const DEVICE = "22222222-2222-4222-8222-000000000002"
const event = {
  subscription_id: DEVICE,
  notification_id: 17,
  conversation_id: CHAT,
  title: "Needs attention",
  body: "SampleSite",
  silent: false,
}

const worker = () => {
  const handlers = new Map<string, (event: unknown) => void>()
  const stored = new Map<string, Response>()
  const shown: Array<{ title: string; options: NotificationOptions }> = []
  const opened: string[] = []
  const windows: Array<{
    url: string
    visibilityState: string
    focused: boolean
    postMessage: (message: unknown) => void
  }> = []
  const self = {
    location: { origin: "https://staff.example" },
    addEventListener: (name: string, handler: (event: unknown) => void) =>
      handlers.set(name, handler),
    registration: {
      showNotification: async (title: string, options: NotificationOptions) => {
        shown.push({ title, options })
      },
      getNotifications: async ({ tag }: { tag: string }) =>
        shown.filter((item) => item.options.tag === tag),
    },
    clients: {
      matchAll: async () => windows,
      openWindow: async (url: string) => {
        opened.push(url)
      },
      claim: async () => {},
    },
    skipWaiting: async () => {},
  }
  vm.runInNewContext(readFileSync(`${process.cwd()}/public/staff-push-sw.js`, "utf8"), {
    self,
    URL,
    Response,
    caches: {
      open: async () => ({
        match: async (key: string) => stored.get(key)?.clone(),
        put: async (key: string, response: Response) => {
          stored.set(key, response)
        },
        delete: async (key: string) => stored.delete(key),
      }),
    },
  })
  const dispatch = async (name: string, details: object) => {
    let finished = Promise.resolve()
    const handler = handlers.get(name)
    if (!handler) throw new Error(`No ${name} handler`)
    handler({
      ...details,
      waitUntil: (promise: Promise<void>) => {
        finished = promise
      },
    })
    await finished
  }
  const configure = (config: object | null) =>
    dispatch("message", {
      source: { url: "https://staff.example/admin/settings" },
      data: { type: "supportchat.push.configure", config },
      ports: [{ postMessage: () => {} }],
    })
  return { dispatch, configure, shown, opened, windows }
}

test("push displays metadata and system sound without storing transcripts", async () => {
  const app = worker()
  await app.configure({ subscription_id: DEVICE, silent: false })
  await app.dispatch("push", { data: { json: () => event } })
  expect(app.shown).toHaveLength(1)
  expect(app.shown[0]).toMatchObject({
    title: "Needs attention",
    options: {
      body: "SampleSite",
      silent: false,
      tag: `supportchat:${DEVICE}:17`,
      data: { url: `https://staff.example/admin/inbox?conversation=${CHAT}` },
    },
  })
})

test("chat alerts offer a view-chat action and examples offer an inbox action", async () => {
  const app = worker()
  await app.configure({ subscription_id: DEVICE, silent: false })
  await app.dispatch("push", { data: { json: () => event } })
  expect(app.shown[0]?.options).toMatchObject({
    actions: [{ action: "open_inbox", title: "View chat" }],
  })
  await app.dispatch("push", {
    data: { json: () => ({ ...event, notification_id: "test-18", conversation_id: null }) },
  })
  expect(app.shown[1]?.options).toMatchObject({
    actions: [{ action: "open_inbox", title: "Open inbox" }],
  })
})

test("muted device stays silent and a logged-out or different account never sees a stale push", async () => {
  const app = worker()
  await app.configure({ subscription_id: DEVICE, silent: true })
  await app.dispatch("push", { data: { json: () => event } })
  expect(app.shown[0]?.options.silent).toBe(true)
  await app.configure(null)
  await app.dispatch("push", { data: { json: () => event } })
  await app.configure({ subscription_id: "33333333-3333-4333-8333-000000000003", silent: false })
  await app.dispatch("push", { data: { json: () => event } })
  expect(app.shown).toHaveLength(1)
})

test("a focused inbox receives a refresh and one push alert", async () => {
  const app = worker()
  await app.configure({ subscription_id: DEVICE, silent: false })
  const messages: unknown[] = []
  app.windows.push({
    url: "https://staff.example/admin/inbox",
    visibilityState: "visible",
    focused: true,
    postMessage: (message) => messages.push(message),
  })
  await app.dispatch("push", { data: { json: () => event } })
  expect(app.shown).toHaveLength(1)
  expect(messages).toContainEqual({ type: "supportchat.push" })
})

test("click opens the chat and never follows a foreign URL", async () => {
  const app = worker()
  await app.dispatch("notificationclick", {
    notification: {
      close: () => {},
      data: { url: `https://staff.example/admin/inbox?conversation=${CHAT}` },
    },
  })
  await app.dispatch("notificationclick", {
    notification: { close: () => {}, data: { url: "https://evil.example" } },
  })
  expect(app.opened).toEqual([`https://staff.example/admin/inbox?conversation=${CHAT}`])
})

test("simultaneous duplicate pushes display only one system alert", async () => {
  const app = worker()
  await app.configure({ subscription_id: DEVICE, silent: false })
  await Promise.all([
    app.dispatch("push", { data: { json: () => event } }),
    app.dispatch("push", { data: { json: () => event } }),
  ])
  expect(app.shown).toHaveLength(1)
})

test("a delivered push test signals one staff window for sound, once, while muted tests stay silent", async () => {
  const app = worker()
  const first: unknown[] = []
  const second: unknown[] = []
  app.windows.push(
    {
      url: "https://staff.example/admin/notifications",
      visibilityState: "visible",
      focused: true,
      postMessage: (message) => first.push(message),
    },
    {
      url: "https://staff.example/admin/inbox",
      visibilityState: "hidden",
      focused: false,
      postMessage: (message) => second.push(message),
    },
  )
  await app.configure({ subscription_id: DEVICE, silent: false })
  const testPayload = { ...event, notification_id: "test-18", conversation_id: null }
  await app.dispatch("push", { data: { json: () => testPayload } })
  await app.dispatch("push", { data: { json: () => testPayload } })
  expect(app.shown).toHaveLength(1)
  expect(
    first.filter(
      (message) =>
        typeof message === "object" &&
        message !== null &&
        "type" in message &&
        message.type === "supportchat.push.test",
    ),
  ).toEqual([{ type: "supportchat.push.test" }])
  expect(
    second.filter(
      (message) =>
        typeof message === "object" &&
        message !== null &&
        "type" in message &&
        message.type === "supportchat.push.test",
    ),
  ).toEqual([])
  await app.configure({ subscription_id: DEVICE, silent: true })
  await app.dispatch("push", {
    data: { json: () => ({ ...testPayload, notification_id: "test-19" }) },
  })
  expect(app.shown[1]?.options.silent).toBe(true)
  expect(
    first.filter(
      (message) =>
        typeof message === "object" &&
        message !== null &&
        "type" in message &&
        message.type === "supportchat.push.test",
    ),
  ).toHaveLength(1)
})
