import type { TranscriptLine } from "./transcript"

export type ConversationState = "prechat" | "bot" | "queued" | "human" | "closed"

export type ChatView = {
  conversation: ConversationState | null
  assignedName: string | null
  lines: TranscriptLine[]
  lastEventId: number
  typing: boolean
}

export const emptyChat = (): ChatView => ({
  conversation: null,
  assignedName: null,
  lines: [],
  lastEventId: 0,
  typing: false,
})

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

const STATES = new Set<ConversationState>(["prechat", "bot", "queued", "human", "closed"])

const applyState = (view: ChatView, frame: Record<string, unknown>): ChatView => {
  if (typeof frame.state !== "string" || !STATES.has(frame.state as ConversationState)) {
    return view
  }
  if (frame.state === "prechat") {
    return {
      conversation: "prechat",
      assignedName: null,
      lines: [],
      lastEventId: 0,
      typing: false,
    }
  }
  let assignedName = view.assignedName
  if (isRecord(frame.assigned_agent) && typeof frame.assigned_agent.display_name === "string") {
    assignedName = frame.assigned_agent.display_name
  }
  if (frame.assigned_agent === null) {
    assignedName = null
  }
  return { ...view, conversation: frame.state as ConversationState, assignedName }
}

const applyMessage = (view: ChatView, frame: Record<string, unknown>): ChatView => {
  if (
    typeof frame.id !== "number" ||
    typeof frame.role !== "string" ||
    typeof frame.body !== "string"
  ) {
    return view
  }
  if (view.lines.some((line) => line.id === frame.id)) {
    return view
  }
  const sourceChunkIds = Array.isArray(frame.source_chunk_ids)
    ? frame.source_chunk_ids.filter((item): item is string => typeof item === "string")
    : null
  const sourceUrls = Array.isArray(frame.source_urls)
    ? frame.source_urls.filter((item): item is string => typeof item === "string")
    : null
  const displayLocator = typeof frame.display_locator === "string" ? frame.display_locator : null
  const sourceTitle = typeof frame.source_title === "string" ? frame.source_title : null
  const systemReason = typeof frame.system_reason === "string" ? frame.system_reason : null
  const lines = [
    ...view.lines,
    {
      id: frame.id,
      role: frame.role,
      body: frame.body,
      source_chunk_ids: sourceChunkIds,
      source_urls: sourceUrls,
      display_locator: displayLocator,
      source_title: sourceTitle,
      system_reason: systemReason,
    },
  ].toSorted((left, right) => left.id - right.id)
  return { ...view, lines, lastEventId: Math.max(view.lastEventId, frame.id) }
}

export const applyVisitorFrame = (view: ChatView, frame: unknown): ChatView => {
  if (!isRecord(frame) || typeof frame.type !== "string") {
    return view
  }
  if (frame.type === "state") {
    return applyState(view, frame)
  }
  if (frame.type === "message") {
    return applyMessage(view, frame)
  }
  if (frame.type === "typing" && typeof frame.active === "boolean") {
    return { ...view, typing: frame.active }
  }
  return view
}

export const isPrechatAccepted = (frame: unknown): boolean => {
  return isRecord(frame) && frame.type === "prechat_accepted"
}

export const isAck = (frame: unknown): boolean => {
  return isRecord(frame) && frame.type === "ack"
}

export const isErrorFrame = (frame: unknown): boolean => {
  return isRecord(frame) && frame.type === "error"
}
