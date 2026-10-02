export type GapRecord = {
  id: string
  site_id: string
  question: string
  conversations: number
  last_seen_at: string
  examples: string[]
  spiking: boolean
  note: string | null
  status: string
  resolved_at: string | null
}

export type GapQueue = {
  items: GapRecord[]
  min_conversations: number
  window_days: number
  spike_conversations: number
  spike_hours: number
}

export type GapView = "open" | "answered" | "dismissed"

export type ClosestCanned = {
  id: string
  site_id: string | null
  shortcut: string
  excerpt: string
  enabled: boolean
  bot_eligible: boolean
  similarity: number
}

export type ClosestKnowledge = {
  title: string
  heading: string
  url: string
  similarity: number
}

export type SimilarEntries = {
  canned: ClosestCanned | null
  knowledge: ClosestKnowledge | null
}

export type AnswerKind = "canned" | "knowledge"

export type AnswerPayload =
  | { kind: "canned"; shortcut: string; body: string }
  | { kind: "knowledge"; title: string; body: string }

export const ANSWER_MAX = 20000
// Past this length a reply is reference material, not something to send word for word.
const KNOWLEDGE_MIN_CHARS = 500
const SHORTCUT_MAX = 40
const SHORTCUT_WORDS = 3
const FILLER_WORDS = new Set([
  "a",
  "an",
  "the",
  "how",
  "do",
  "does",
  "did",
  "i",
  "we",
  "you",
  "my",
  "our",
  "your",
  "me",
  "us",
  "is",
  "are",
  "was",
  "what",
  "where",
  "when",
  "why",
  "which",
  "who",
  "can",
  "could",
  "to",
  "of",
  "for",
  "in",
  "on",
  "at",
  "and",
  "or",
  "it",
  "this",
  "that",
])

export const recommendedKind = (answer: string): AnswerKind =>
  answer.trim().length > KNOWLEDGE_MIN_CHARS ? "knowledge" : "canned"

export const suggestShortcut = (question: string) => {
  const words = (question.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(
    (word) => !FILLER_WORDS.has(word),
  )
  const shortcut = words
    .slice(0, SHORTCUT_WORDS)
    .join("_")
    .slice(0, SHORTCUT_MAX)
    .replace(/_+$/, "")
  return shortcut || "faq"
}

export const formatDay = (value: string) =>
  new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value))

export const chatCount = (count: number) => `${count} ${count === 1 ? "chat" : "chats"}`

export const KNOWLEDGE_HREF = "/admin/knowledge"

export const cannedEditHref = (canned: ClosestCanned) =>
  `/admin/canned-responses?scope=${canned.site_id ?? "general"}&q=${encodeURIComponent(canned.shortcut)}`

export const handledLabel = (status: string) => {
  if (status === "knowledge") return "Saved as knowledge text"
  if (status === "canned") return "Saved as a quick reply"
  return "Dismissed"
}
