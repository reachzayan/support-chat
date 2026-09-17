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
  queued: Outgoing[]
}

const sendJson = (transport: Transport, frame: Outgoing) => {
  if (transport.live && transport.socket !== null && transport.socket.readyState === AUTH_OPEN) {
    transport.socket.send(JSON.stringify(frame))
    return
  }
  transport.queued.push(frame)
}

const flushQueued = (transport: Transport) => {
  const pending = transport.queued.splice(0, transport.queued.length)
  for (const frame of pending) {
    if (transport.socket !== null && transport.socket.readyState === AUTH_OPEN) {
      transport.socket.send(JSON.stringify(frame))
    }
  }
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
  onFrame: (frame: unknown) => void,
) => {
  return (event: MessageEvent) => {
    const frame = parseSocketFrame(event)
    if (frame === null) {
      return
    }
    dropAck(unacked, frame)
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
) => {
  const handleMessage = createMessageHandler(transport, unacked, options.onFrame)
  return (next: WebSocket) => {
    transport.live = false
    transport.socket = next
    /* oxlint-disable unicorn/prefer-add-event-listener -- FakeSocket tests assign onopen */
    next.onopen = () => {
      transport.live = true
      authenticate()
      flushQueued(transport)
    }
    next.onmessage = handleMessage
    next.onclose = (event: CloseEvent) => options.onClose(event.code)
    /* oxlint-enable unicorn/prefer-add-event-listener */
  }
}

const createAgentApi = (
  transport: Transport,
  unacked: Unacked[],
  attach: (next: WebSocket) => void,
  url: string,
  setToken: (next: string) => void,
) => ({
  subscribe: (conversation_id: string, last_event_id: number) => {
    sendJson(transport, { v: 1, type: "subscribe", conversation_id, last_event_id })
  },
  join: (conversation_id: string) => {
    sendJson(transport, { v: 1, type: "join", conversation_id })
  },
  closeAttention: (conversation_id: string) => {
    sendJson(transport, { v: 1, type: "close_attention", conversation_id })
  },
  end: (conversation_id: string) => {
    sendJson(transport, { v: 1, type: "end", conversation_id })
  },
  transferToBot: (conversation_id: string) => {
    sendJson(transport, { v: 1, type: "transfer_to_bot", conversation_id })
  },
  sendMessage: (conversation_id: string, client_message_id: string, body: string) => {
    unacked.push({ conversation_id, client_message_id, body })
    sendJson(transport, {
      v: 1,
      type: "message",
      conversation_id,
      client_message_id,
      body,
    })
  },
  reconnect: () => {
    const previous = transport.socket
    if (previous !== null) {
      /* oxlint-disable-next-line unicorn/prefer-add-event-listener -- detach FakeSocket onclose */
      previous.onclose = null
      previous.close(1000)
    }
    attach(new WebSocket(url))
  },
  flushUnacked: () => {
    for (const item of unacked) {
      sendJson(transport, {
        v: 1,
        type: "message",
        conversation_id: item.conversation_id,
        client_message_id: item.client_message_id,
        body: item.body,
      })
    }
  },
  setAccessToken: setToken,
  close: () => transport.socket?.close(1000),
})

export const createAgentSocket = (options: AgentSocketOptions) => {
  let token = options.accessToken
  const transport: Transport = { socket: null, live: false, queued: [] }
  const unacked: Unacked[] = []
  const authenticate = () => {
    sendJson(transport, { v: 1, type: "auth", access_token: token })
  }
  const attach = createSocketBinder(transport, options, authenticate, unacked)
  attach(new WebSocket(options.url))
  return createAgentApi(transport, unacked, attach, options.url, (next) => {
    token = next
  })
}

const dropAck = (unacked: Unacked[], frame: unknown) => {
  if (!isRecord(frame) || frame.type !== "ack" || typeof frame.client_message_id !== "string") {
    return
  }
  const index = unacked.findIndex((item) => item.client_message_id === frame.client_message_id)
  if (index >= 0) {
    unacked.splice(index, 1)
  }
}
