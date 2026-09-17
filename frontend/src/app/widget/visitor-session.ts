import type { SourceCitation } from "./source-hovercard"
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

export const applyConversationSnapshot = (
  view: ChatView,
  snapshot: {
    state: ConversationState
    assigned_agent: { id: string; display_name: string } | null
    messages: unknown[]
  },
): ChatView => {
  let next = view
  for (const message of snapshot.messages) {
    next = applyVisitorFrame(next, message)
  }
  return applyVisitorFrame(next, {
    type: "state",
    state: snapshot.state,
    assigned_agent: snapshot.assigned_agent,
  })
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

const citationFromRecord = (item: unknown): SourceCitation | null => {
  if (!isRecord(item)) {
    return null
  }
  const sourceUrl = typeof item.source_url === "string" ? item.source_url : null
  const sourceTitle = typeof item.source_title === "string" ? item.source_title : null
  if (!sourceUrl && !sourceTitle) {
    return null
  }
  return {
    source_urls: sourceUrl ? [sourceUrl] : null,
    source_title: sourceTitle,
  }
}

const citationsFromFrame = (value: unknown): SourceCitation[] =>
  Array.isArray(value)
    ? value.flatMap((item) => {
        const citation = citationFromRecord(item)
        return citation ? [citation] : []
      })
    : []

const stringList = (value: unknown): string[] | null =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : null

const nullableString = (value: unknown): string | null => (typeof value === "string" ? value : null)

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
  const sourceChunkIds = stringList(frame.source_chunk_ids)
  const sourceUrls = stringList(frame.source_urls)
  const displayLocator = nullableString(frame.display_locator)
  const sourceTitle = nullableString(frame.source_title)
  const systemReason = nullableString(frame.system_reason)
  const responseOutcome = nullableString(frame.response_outcome)
  const reasonCode = nullableString(frame.reason_code)
  const createdAt = nullableString(frame.created_at)
  const lines = [
    ...view.lines,
    {
      id: frame.id,
      role: frame.role,
      body: frame.body,
      created_at: createdAt,
      source_chunk_ids: sourceChunkIds,
      source_urls: sourceUrls,
      display_locator: displayLocator,
      source_title: sourceTitle,
      system_reason: systemReason,
      response_outcome: responseOutcome,
      reason_code: reasonCode,
      citations: citationsFromFrame(frame.citations),
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
