type Unacked = {
  client_message_id: string
  body: string
}

type VisitorSocketOptions = {
  url: string
  bootstrapToken: string
  parentOrigin: string
  onFrame: (frame: unknown) => void
  onClose: (code: number) => void
}

type Outgoing = Record<string, unknown>

const AUTH_OPEN = 1

export const visitorSocketUrl = (
  apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://127.0.0.1:8000",
) => {
  const url = new URL(apiOrigin)
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  url.pathname = "/ws/visitor"
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

export const createVisitorSocket = (options: VisitorSocketOptions) => {
  let token = options.bootstrapToken
  const transport: Transport = { socket: null, live: false, queued: [] }
  const unacked: Unacked[] = []

  const authenticate = () => {
    sendJson(transport, {
      v: 1,
      type: "auth",
      bootstrap_token: token,
      parent_origin: options.parentOrigin,
    })
  }

  const handleMessage = (event: MessageEvent) => {
    let frame: unknown
    try {
      frame = JSON.parse(String(event.data)) as unknown
    } catch {
      return
    }
    dropAck(unacked, frame)
    if (isRecord(frame) && frame.type === "ping") {
      sendJson(transport, { v: 1, type: "pong" })
    }
    options.onFrame(frame)
  }

  const attach = (next: WebSocket) => {
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

  attach(new WebSocket(options.url))

  return {
    sendMessage: (client_message_id: string, body: string) => {
      unacked.push({ client_message_id, body })
      sendJson(transport, { v: 1, type: "message", client_message_id, body })
    },
    sendPrechat: (fields: Record<string, string>) =>
      sendJson(transport, { v: 1, type: "prechat", ...fields }),
    sendHello: (page_url: string, page_title: string, referrer: string) => {
      sendJson(transport, { v: 1, type: "hello", page_url, page_title, referrer })
    },
    sendEscalate: () => sendJson(transport, { v: 1, type: "escalate" }),
    resume: (last_event_id: number) => sendJson(transport, { v: 1, type: "resume", last_event_id }),
    reconnect: () => {
      const previous = transport.socket
      if (previous !== null) {
        /* oxlint-disable-next-line unicorn/prefer-add-event-listener -- detach FakeSocket onclose */
        previous.onclose = null
        previous.close(1000)
      }
      attach(new WebSocket(options.url))
    },
    flushUnacked: () => {
      for (const item of unacked) {
        sendJson(transport, {
          v: 1,
          type: "message",
          client_message_id: item.client_message_id,
          body: item.body,
        })
      }
    },
    setBootstrapToken: (next: string) => {
      token = next
    },
    close: () => transport.socket?.close(1000),
  }
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
