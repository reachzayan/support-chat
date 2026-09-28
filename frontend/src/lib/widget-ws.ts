/* oxlint-disable max-lines-per-function, complexity -- socket lifecycle and retry state share one owner */
type Unacked = {
  client_message_id: string
  body: string
}

type VisitorSocketOptions = {
  url: string
  bootstrapToken: string
  parentOrigin: string
  lastEventId?: number
  conversationId?: string | null
  onFrame: (frame: unknown) => void
  onClose: (code: number) => void
}

import { resolvePublicApiOrigin } from "./api-origin"

type Outgoing = Record<string, unknown>

const AUTH_OPEN = 1

export const visitorSocketUrl = (apiOrigin?: string) => {
  const url = new URL(resolvePublicApiOrigin(apiOrigin))
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = "/ws/visitor"
  url.search = ""
  url.hash = ""
  return url.toString()
}

type Transport = {
  socket: WebSocket | null
  live: boolean
  queued: Map<string, Outgoing>
}

const MAX_PENDING_MESSAGES = 32
const MAX_QUEUED_COMMANDS = 8

const sendJson = (transport: Transport, frame: Outgoing, key = String(frame.type)) => {
  if (transport.live && transport.socket !== null && transport.socket.readyState === AUTH_OPEN) {
    transport.socket.send(JSON.stringify(frame))
    return
  }
  if (key === "pong") {
    return
  }
  if (!transport.queued.has(key) && transport.queued.size >= MAX_QUEUED_COMMANDS) {
    transport.queued.delete(transport.queued.keys().next().value ?? "")
  }
  transport.queued.set(key, frame)
}

const flushQueued = (transport: Transport) => {
  if (transport.socket === null || transport.socket.readyState !== AUTH_OPEN) {
    return
  }
  for (const frame of transport.queued.values()) {
    transport.socket.send(JSON.stringify(frame))
  }
  transport.queued.clear()
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

export const createVisitorSocket = (options: VisitorSocketOptions) => {
  let token = options.bootstrapToken
  let lastEventId = options.lastEventId ?? 0
  let conversationId = options.conversationId ?? null
  const transport: Transport = { socket: null, live: false, queued: new Map() }
  const unacked: Unacked[] = []
  const sentOnConnection = new Set<string>()
  let pendingPrechat: ({ submission_id: string } & Record<string, string>) | null = null

  const flushUnacked = () => {
    if (!transport.live || transport.socket?.readyState !== AUTH_OPEN) {
      return
    }
    for (const item of unacked) {
      if (sentOnConnection.has(item.client_message_id)) {
        continue
      }
      transport.socket.send(
        JSON.stringify({
          v: 1,
          type: "message",
          client_message_id: item.client_message_id,
          body: item.body,
        }),
      )
      sentOnConnection.add(item.client_message_id)
    }
  }

  const authenticate = () => {
    sendJson(transport, {
      v: 1,
      type: "auth",
      bootstrap_token: token,
      parent_origin: options.parentOrigin,
      last_event_id: lastEventId,
    })
  }

  const handleMessage = (event: MessageEvent) => {
    let frame: unknown
    try {
      frame = JSON.parse(String(event.data)) as unknown
    } catch {
      return
    }
    dropAck(unacked, sentOnConnection, frame)
    if (isRecord(frame) && frame.type === "message" && typeof frame.id === "number") {
      lastEventId = Math.max(lastEventId, frame.id)
    }
    if (
      isRecord(frame) &&
      frame.type === "prechat_accepted" &&
      frame.submission_id === pendingPrechat?.submission_id
    ) {
      pendingPrechat = null
    }
    if (isRecord(frame) && frame.type === "error") {
      pendingPrechat = null
    }
    if (isRecord(frame) && frame.type === "ping") {
      sendJson(transport, { v: 1, type: "pong" })
    }
    options.onFrame(frame)
  }

  const attach = (next: WebSocket) => {
    transport.live = false
    transport.socket = next
    sentOnConnection.clear()
    /* oxlint-disable unicorn/prefer-add-event-listener -- FakeSocket tests assign onopen */
    next.onopen = () => {
      transport.live = true
      authenticate()
      flushQueued(transport)
      if (pendingPrechat !== null) {
        sendJson(transport, { v: 1, type: "prechat", ...pendingPrechat })
      }
      flushUnacked()
    }
    next.onmessage = handleMessage
    next.onclose = (event: CloseEvent) => {
      transport.live = false
      options.onClose(event.code)
    }
    /* oxlint-enable unicorn/prefer-add-event-listener */
  }

  attach(new WebSocket(options.url))

  return {
    sendMessage: (client_message_id: string, body: string) => {
      if (unacked.length >= MAX_PENDING_MESSAGES) {
        options.onFrame({ v: 1, type: "error", code: "queue_full" })
        return false
      }
      unacked.push({ client_message_id, body })
      flushUnacked()
      return true
    },
    sendPrechat: (fields: { submission_id: string } & Record<string, string>) => {
      if (pendingPrechat !== null) {
        return
      }
      pendingPrechat = fields
      if (transport.live) {
        sendJson(transport, { v: 1, type: "prechat", ...fields })
      }
    },
    sendHello: (page_url: string, page_title: string, referrer: string) => {
      sendJson(transport, { v: 1, type: "hello", page_url, page_title, referrer })
    },
    sendEscalate: () => sendJson(transport, { v: 1, type: "escalate" }),
    resume: (last_event_id: number) => sendJson(transport, { v: 1, type: "resume", last_event_id }),
    loadOlder: (before_id: number) => sendJson(transport, { v: 1, type: "older", before_id }),
    reconnect: () => {
      const previous = transport.socket
      if (previous !== null) {
        /* oxlint-disable-next-line unicorn/prefer-add-event-listener -- detach FakeSocket onclose */
        previous.onclose = null
        /* oxlint-disable unicorn/prefer-add-event-listener -- detach stale socket handlers */
        previous.onmessage = null
        previous.onopen = null
        /* oxlint-enable unicorn/prefer-add-event-listener */
        previous.close(1000)
      }
      attach(new WebSocket(options.url))
    },
    flushUnacked,
    setBootstrapToken: (next: string) => {
      token = next
    },
    setBootstrapCursor: (next: number) => {
      lastEventId = next
    },
    setConversationId: (next: string | null) => {
      if (conversationId !== next) {
        conversationId = next
        unacked.length = 0
        sentOnConnection.clear()
        pendingPrechat = null
        transport.queued.clear()
      }
    },
    close: () => {
      const current = transport.socket
      transport.live = false
      transport.socket = null
      if (current !== null) {
        /* oxlint-disable unicorn/prefer-add-event-listener -- detach discarded socket handlers */
        current.onmessage = null
        current.onopen = null
        current.onclose = null
        /* oxlint-enable unicorn/prefer-add-event-listener */
        current.close(1000)
      }
    },
    isOpen: () =>
      transport.live && transport.socket !== null && transport.socket.readyState === AUTH_OPEN,
  }
}

const dropAck = (unacked: Unacked[], sentOnConnection: Set<string>, frame: unknown) => {
  if (!isRecord(frame) || frame.type !== "ack" || typeof frame.client_message_id !== "string") {
    return
  }
  const index = unacked.findIndex((item) => item.client_message_id === frame.client_message_id)
  if (index >= 0) {
    unacked.splice(index, 1)
    sentOnConnection.delete(frame.client_message_id)
  }
}
