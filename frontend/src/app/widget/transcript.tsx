"use client"

import { useEffect, useRef, useState } from "react"

import { SourceHoverCard, type SourceCitation } from "./source-hovercard"

export type TranscriptLine = {
  id: number
  role: string
  body: string
  created_at?: string | null
  source_chunk_ids?: string[] | null
  source_urls?: string[] | null
  display_locator?: string | null
  source_title?: string | null
  system_reason?: string | null
  response_outcome?: string | null
  reason_code?: string | null
  citations?: SourceCitation[]
}

export type TranscriptSelfRole = "visitor" | "agent"

type TranscriptConversationState = "prechat" | "bot" | "queued" | "human" | "closed"

type TranscriptProps = {
  lines: TranscriptLine[]
  typing?: boolean
  notice?: string
  selfRole?: TranscriptSelfRole
  logLabel?: string
  autoFollow?: boolean
  muted?: boolean
  conversationState?: TranscriptConversationState | null
}

const IDLE_WARNING = "This chat will be closed in one minute. Send any message to keep active."

const IDLE_WARN_MS = 4 * 60 * 1000
const IDLE_CLOSE_MS = 5 * 60 * 1000
const IDLE_TICK_MS = 15_000

export const isClosedNotice = (line: TranscriptLine) => {
  if (line.role !== "system") {
    return false
  }
  return /^(this chat is closed|this chat was closed by .+)\.?$/i.test(line.body.trim())
}

export const isCenteredNotice = (line: TranscriptLine) => {
  if (line.role !== "system") {
    return false
  }
  return (
    isClosedNotice(line) ||
    /^(a human has joined)\.?$/i.test(line.body.trim()) ||
    /^you(?:'|’)re now chatting with .+\.?$/i.test(line.body.trim())
  )
}

const selfBubble =
  "ml-auto max-w-[82%] rounded-[20px] rounded-br-[6px] bg-steel/15 px-4 py-2 text-sm leading-5 text-ink"
const otherBubble =
  "mr-auto max-w-[82%] rounded-[20px] rounded-bl-[6px] bg-paper px-4 py-2 text-sm leading-5 text-ink shadow-[0_1px_3px_rgba(13,31,58,0.08)]"
const noticeClass =
  "mx-auto max-w-[92%] rounded-full bg-ice-2 px-3 py-1 text-center text-[11px] leading-5 text-mute"
const idleWarningClass =
  "mx-auto max-w-[92%] rounded-[8px] bg-ice-2 px-3 py-2 text-center text-xs leading-5 text-mute motion-safe:transition-opacity motion-safe:duration-200"

const useAutoFollow = (enabled: boolean, latestLineId: number | undefined) => {
  const latestRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!enabled || latestLineId === undefined) {
      return
    }
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false
    latestRef.current?.scrollIntoView?.({
      behavior: reducedMotion ? "auto" : "smooth",
      block: "end",
    })
  }, [enabled, latestLineId])
  return latestRef
}

const lastVisitorCreatedAt = (lines: TranscriptLine[]) => {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]
    if (line.role === "visitor" && line.created_at) {
      return line.created_at
    }
  }
  return null
}

const isIdleWarningDue = (
  conversationState: TranscriptConversationState | null | undefined,
  lines: TranscriptLine[],
  nowMs: number,
) => {
  if (conversationState !== "bot" && conversationState !== "human") {
    return false
  }
  const createdAt = lastVisitorCreatedAt(lines)
  if (!createdAt) {
    return false
  }
  const createdMs = Date.parse(createdAt)
  if (Number.isNaN(createdMs)) {
    return false
  }
  const idleMs = nowMs - createdMs
  return idleMs >= IDLE_WARN_MS && idleMs < IDLE_CLOSE_MS
}

const useIdleWarning = (
  conversationState: TranscriptConversationState | null | undefined,
  lines: TranscriptLine[],
) => {
  const [visible, setVisible] = useState(() =>
    isIdleWarningDue(conversationState, lines, Date.now()),
  )
  useEffect(() => {
    const refresh = () => {
      setVisible(isIdleWarningDue(conversationState, lines, Date.now()))
    }
    refresh()
    const timer = window.setInterval(refresh, IDLE_TICK_MS)
    return () => window.clearInterval(timer)
  }, [conversationState, lines])
  return visible
}

const bubbleClass = (line: TranscriptLine, selfRole: TranscriptSelfRole) => {
  if (isCenteredNotice(line)) {
    return noticeClass
  }
  const responderOnRight =
    line.role === selfRole ||
    (selfRole === "agent" &&
      (line.role === "agent" || line.role === "admin" || line.role === "bot"))
  if (responderOnRight) {
    return selfBubble
  }
  return otherBubble
}

const roleLabel = (line: TranscriptLine, selfRole: TranscriptSelfRole) => {
  if (isCenteredNotice(line) || line.role === selfRole) {
    return null
  }
  if (line.role === "visitor") {
    return "Visitor"
  }
  if (line.role === "admin") {
    return "Admin"
  }
  if (line.role === "bot") {
    return "Assistant"
  }
  return "Agent"
}

const hasSource = (line: TranscriptLine) => {
  if (line.citations?.length) {
    return true
  }
  if (line.role !== "bot") {
    return false
  }
  return Boolean(line.source_chunk_ids?.length || line.source_urls?.length)
}

const citationFromLine = (line: TranscriptLine): SourceCitation => ({
  source_urls: line.source_urls,
  display_locator: line.display_locator,
  source_title: line.source_title,
})

const citationsFromLine = (line: TranscriptLine): SourceCitation[] =>
  line.citations?.length ? line.citations : [citationFromLine(line)]

const sourceLabel = (_line: TranscriptLine) => "Source"

const TranscriptRow = ({
  line,
  selfRole,
}: {
  line: TranscriptLine
  selfRole: TranscriptSelfRole
}) => {
  const label = roleLabel(line, selfRole)
  const messageId = `transcript-msg-${line.id}`
  return (
    <div className={`${bubbleClass(line, selfRole)} widget-bubble break-words whitespace-pre-wrap`}>
      {label ? (
        <span className="mb-1.5 block text-[10px] font-bold tracking-[0.08em] uppercase opacity-70">
          {label}
        </span>
      ) : null}
      <p id={messageId}>{line.body}</p>
      {hasSource(line) ? (
        <span className="mt-2 flex flex-wrap gap-2">
          {citationsFromLine(line).map((citation, index) => (
            <SourceHoverCard
              key={`${citation.source_urls?.[0] ?? citation.source_title ?? "source"}-${citation.cited_text ?? ""}`}
              citation={citation}
              describedBy={messageId}
              label={`${sourceLabel(line)} ${index + 1}`}
            />
          ))}
        </span>
      ) : null}
    </div>
  )
}

const TypingNotice = () => (
  <p className="text-mute flex items-center gap-2 px-1 text-xs" aria-live="polite">
    <span className="bg-steel size-1.5 rounded-full" />
    Assistant is typing…
  </p>
)

const IdleWarningPill = () => <output className={idleWarningClass}>{IDLE_WARNING}</output>

const isEmptyTranscript = (
  lines: TranscriptLine[],
  typing: boolean,
  notice: string | undefined,
  logLabel: string | undefined,
) => lines.length === 0 && !typing && notice === undefined && logLabel === undefined

const transcriptSurface = (muted: boolean) => (muted ? "bg-ice-2/55" : "bg-transparent")

const TranscriptContent = ({
  lines,
  typing,
  notice,
  selfRole,
  latestRef,
  showIdleWarning,
}: {
  lines: TranscriptLine[]
  typing: boolean
  notice?: string
  selfRole: TranscriptSelfRole
  latestRef: ReturnType<typeof useAutoFollow>
  showIdleWarning: boolean
}) => (
  <>
    {lines.map((line) => (
      <TranscriptRow key={line.id} line={line} selfRole={selfRole} />
    ))}
    {notice === undefined ? null : <p className={`${noticeClass} widget-bubble`}>{notice}</p>}
    {showIdleWarning ? <IdleWarningPill /> : null}
    {typing ? <TypingNotice /> : null}
    <div ref={latestRef} aria-hidden="true" />
  </>
)

export const Transcript = ({
  lines,
  typing = false,
  notice,
  selfRole = "visitor",
  logLabel,
  autoFollow = false,
  muted = false,
  conversationState = null,
}: TranscriptProps) => {
  const latestRef = useAutoFollow(autoFollow, lines.at(-1)?.id)
  const showIdleWarning = useIdleWarning(conversationState, lines)
  const surface = transcriptSurface(muted)
  if (isEmptyTranscript(lines, typing, notice, logLabel)) {
    return <div aria-live="polite" className={`min-h-0 flex-1 ${surface}`} />
  }
  const logRole = logLabel === undefined ? undefined : "log"
  return (
    <div
      role={logRole}
      aria-label={logLabel}
      aria-live="polite"
      className={`flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-5 py-5 ${surface}`}
    >
      <TranscriptContent
        lines={lines}
        typing={typing}
        notice={notice}
        selfRole={selfRole}
        latestRef={latestRef}
        showIdleWarning={showIdleWarning}
      />
    </div>
  )
}
