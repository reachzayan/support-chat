type Unacked = {
  conversation_id: string
  client_message_id: string
  body: string
}

type AgentSocketOptions = {
  url: string
  accessToken: string
  onFrame: (frame: unknown) => void
  onClose: (code: number) => void
}

import { resolvePublicApiOrigin } from "./api-origin"

type Outgoing = Record<string, unknown>

const AUTH_OPEN = 1

export const agentSocketUrl = (apiOrigin?: string) => {
  const url = new URL(resolvePublicApiOrigin(apiOrigin))
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = "/ws/agent"
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
const MAX_QUEUED_COMMANDS = 32

const sendJson = (transport: Transport, frame: Outgoing) => {
  if (transport.live && transport.socket !== null && transport.socket.readyState === AUTH_OPEN) {
    transport.socket.send(JSON.stringify(frame))
    return true
  }
  if (frame.type === "pong") {
    return true
  }
  const key = `${String(frame.type)}:${String(frame.conversation_id ?? "")}`
  if (!transport.queued.has(key) && transport.queued.size >= MAX_QUEUED_COMMANDS) {
    return false
  }
  transport.queued.set(key, frame)
  return true
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

const parseSocketFrame = (event: MessageEvent) => {
  try {
    return JSON.parse(String(event.data)) as unknown
  } catch {
    return null
  }
}

const createMessageHandler = (
  transport: Transport,
  unacked: Unacked[],
  sentOnConnection: Set<string>,
  onFrame: (frame: unknown) => void,
) => {
  return (event: MessageEvent) => {
    const frame = parseSocketFrame(event)
    if (frame === null) {
      return
    }
    dropAck(unacked, sentOnConnection, frame)
    if (isRecord(frame) && frame.type === "ping") {
      sendJson(transport, { v: 1, type: "pong" })
    }
    onFrame(frame)
  }
}

const createSocketBinder = (
  transport: Transport,
  options: AgentSocketOptions,
  authenticate: () => void,
  unacked: Unacked[],
  sentOnConnection: Set<string>,
  flushUnacked: () => void,
) => {
  const handleMessage = createMessageHandler(transport, unacked, sentOnConnection, options.onFrame)
  return (next: WebSocket) => {
    transport.live = false
    transport.socket = next
    sentOnConnection.clear()
    /* oxlint-disable unicorn/prefer-add-event-listener -- FakeSocket tests assign onopen */
    next.onopen = () => {
      transport.live = true
      authenticate()
      flushQueued(transport)
      flushUnacked()
    }
    next.onmessage = handleMessage
    next.onclose = (event: CloseEvent) => {
      transport.live = false
      options.onClose(event.code)
    }
    /* oxlint-enable unicorn/prefer-add-event-listener */
  }
}

const createAgentApi = (
  transport: Transport,
  unacked: Unacked[],
  flushUnacked: () => void,
  attach: (next: WebSocket) => void,
  url: string,
  setToken: (next: string) => void,
  onFrame: (frame: unknown) => void,
) => {
  const sendCommand = (frame: Outgoing) => {
    if (!sendJson(transport, frame)) {
      onFrame({ v: 1, type: "error", code: "queue_full" })
    }
  }
  return {
    subscribe: (conversation_id: string, last_event_id: number) => {
      transport.queued.delete(`unsubscribe:${conversation_id}`)
      sendCommand({ v: 1, type: "subscribe", conversation_id, last_event_id })
    },
    unsubscribe: (conversation_id: string) => {
      transport.queued.delete(`subscribe:${conversation_id}`)
      if (transport.live) {
        sendCommand({ v: 1, type: "unsubscribe", conversation_id })
      }
    },
    join: (conversation_id: string) => {
      sendCommand({ v: 1, type: "join", conversation_id })
    },
    closeAttention: (conversation_id: string) => {
      sendCommand({ v: 1, type: "close_attention", conversation_id })
    },
    end: (conversation_id: string) => {
      sendCommand({ v: 1, type: "end", conversation_id })
    },
    transferToBot: (conversation_id: string) => {
      sendCommand({ v: 1, type: "transfer_to_bot", conversation_id })
    },
    sendMessage: (conversation_id: string, client_message_id: string, body: string) => {
      if (unacked.length >= MAX_PENDING_MESSAGES) {
        onFrame({ v: 1, type: "error", code: "queue_full" })
        return false
      }
      unacked.push({ conversation_id, client_message_id, body })
      flushUnacked()
      return true
    },
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
      attach(new WebSocket(url))
    },
    flushUnacked,
    setAccessToken: setToken,
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

export const createAgentSocket = (options: AgentSocketOptions) => {
  let token = options.accessToken
  const transport: Transport = { socket: null, live: false, queued: new Map() }
  const unacked: Unacked[] = []
  const sentOnConnection = new Set<string>()
  const flushUnacked = () => {
    if (!transport.live || transport.socket?.readyState !== AUTH_OPEN) {
      return
    }
    for (const item of unacked) {
      if (sentOnConnection.has(item.client_message_id)) {
        continue
      }
      transport.socket.send(JSON.stringify({ v: 1, type: "message", ...item }))
      sentOnConnection.add(item.client_message_id)
    }
  }
  const authenticate = () => {
    sendJson(transport, { v: 1, type: "auth", access_token: token })
  }
  const attach = createSocketBinder(
    transport,
    options,
    authenticate,
    unacked,
    sentOnConnection,
    flushUnacked,
  )
  attach(new WebSocket(options.url))
  return createAgentApi(
    transport,
    unacked,
    flushUnacked,
    attach,
    options.url,
    (next) => {
      token = next
    },
    options.onFrame,
  )
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
