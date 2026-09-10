import type { ConversationDetail, InboxMessage } from "./types"

export type AssignedAgent = {
  id: string
  display_name: string
}

export type InboxLive = {
  chatState: string | null
  assigned: AssignedAgent | null
  joinPending: boolean
  winnerName: string | null
  detail: ConversationDetail | null
  lines: InboxMessage[]
}

export const emptyLive = (): InboxLive => ({
  chatState: null,
  assigned: null,
  joinPending: false,
  winnerName: null,
  detail: null,
  lines: [],
})

export const maxMessageId = (lines: InboxMessage[]) => {
  if (lines.length === 0) {
    return 0
  }
  return Math.max(...lines.map((line) => line.id))
}

export const mergeLine = (lines: InboxMessage[], incoming: InboxMessage) => {
  if (lines.some((line) => line.id === incoming.id)) {
    return lines
  }
  return [...lines, incoming].toSorted((left, right) => left.id - right.id)
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

export type FrameEffect = {
  live: InboxLive
  refetchList: boolean
  refetchDetailId: string | null
}

const idle = (live: InboxLive): FrameEffect => ({
  live,
  refetchList: false,
  refetchDetailId: null,
})

export const applyAgentFrame = (
  live: InboxLive,
  frame: unknown,
  userId: string,
  selectedId: string | null,
): FrameEffect => {
  if (!isRecord(frame) || typeof frame.type !== "string") {
    return idle(live)
  }
  if (frame.type === "inbox_upsert") {
    return applyInboxUpsert(live, frame, selectedId)
  }
  return applySessionFrame(live, frame, userId, selectedId)
}

const applyInboxUpsert = (
  live: InboxLive,
  frame: Record<string, unknown>,
  selectedId: string | null,
): FrameEffect => {
  const conversationId = typeof frame.conversation_id === "string" ? frame.conversation_id : null
  const refetchDetailId = conversationId === selectedId ? conversationId : null
  return { live, refetchList: true, refetchDetailId }
}

const applySessionFrame = (
  live: InboxLive,
  frame: Record<string, unknown>,
  userId: string,
  selectedId: string | null,
): FrameEffect => {
  const scoped = typeof frame.conversation_id === "string" ? frame.conversation_id : null
  if (scoped !== null && scoped !== selectedId) {
    return idle(live)
  }
  if (frame.type === "error" && frame.code === "already_joined") {
    return applyAlreadyJoined(live, frame)
  }
  if (frame.type === "state" && typeof frame.state === "string") {
    return { live: applyState(live, frame, userId), refetchList: false, refetchDetailId: null }
  }
  return applyMessageFrame(live, frame)
}

const applyAlreadyJoined = (live: InboxLive, frame: Record<string, unknown>): FrameEffect => {
  const winnerName = typeof frame.display_name === "string" ? frame.display_name : live.winnerName
  return {
    live: { ...live, joinPending: false, winnerName },
    refetchList: false,
    refetchDetailId: null,
  }
}

const applyMessageFrame = (live: InboxLive, frame: Record<string, unknown>): FrameEffect => {
  const incoming = parseMessage(frame)
  if (incoming === null) {
    return idle(live)
  }
  return {
    live: { ...live, lines: mergeLine(live.lines, incoming) },
    refetchList: false,
    refetchDetailId: null,
  }
}

const applyState = (live: InboxLive, frame: Record<string, unknown>, userId: string): InboxLive => {
  const chatState = String(frame.state)
  let assigned = live.assigned
  let winnerName = live.winnerName
  let detail = live.detail
  if (isRecord(frame.assigned_agent) && typeof frame.assigned_agent.display_name === "string") {
    assigned = {
      id: String(frame.assigned_agent.id ?? ""),
      display_name: frame.assigned_agent.display_name,
    }
    if (detail !== null) {
      detail = { ...detail, assigned_agent: assigned, state: chatState }
    }
    if (assigned.id !== userId) {
      winnerName = assigned.display_name
    }
  } else if (frame.assigned_agent === null) {
    assigned = null
    winnerName = null
    if (detail !== null) {
      detail = { ...detail, assigned_agent: null, state: chatState }
    }
  }
  return {
    ...live,
    chatState,
    assigned,
    winnerName,
    detail,
    joinPending: chatState === "human" ? false : live.joinPending,
  }
}

const asStringList = (value: unknown): string[] | null => {
  if (!Array.isArray(value)) {
    return null
  }
  return value.filter((item): item is string => typeof item === "string")
}

const parseMessage = (frame: Record<string, unknown>): InboxMessage | null => {
  if (frame.type !== "message" || typeof frame.id !== "number" || typeof frame.body !== "string") {
    return null
  }
  return {
    id: frame.id,
    role: typeof frame.role === "string" ? frame.role : "system",
    author_user: null,
    body: frame.body,
    source_article_ids: asStringList(frame.source_article_ids),
    source_chunk_ids: asStringList(frame.source_chunk_ids),
    source_urls: asStringList(frame.source_urls),
    display_locator: typeof frame.display_locator === "string" ? frame.display_locator : null,
    source_title: typeof frame.source_title === "string" ? frame.source_title : null,
    system_reason: typeof frame.system_reason === "string" ? frame.system_reason : null,
    created_at: typeof frame.created_at === "string" ? frame.created_at : "",
  }
}
