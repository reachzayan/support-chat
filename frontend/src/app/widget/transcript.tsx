"use client"

import { useEffect, useRef } from "react"

import { SourceHoverCard, type SourceCitation } from "./source-hovercard"

export type TranscriptLine = {
  id: number
  role: string
  body: string
  source_chunk_ids?: string[] | null
  source_urls?: string[] | null
  display_locator?: string | null
  source_title?: string | null
  system_reason?: string | null
}

export type TranscriptSelfRole = "visitor" | "agent"

type TranscriptProps = {
  lines: TranscriptLine[]
  typing?: boolean
  notice?: string
  selfRole?: TranscriptSelfRole
  logLabel?: string
  autoFollow?: boolean
  muted?: boolean
}

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
  "ml-auto max-w-[82%] rounded-[8px] rounded-br-sm bg-navy px-4 py-3 text-sm leading-6 text-paper"
const otherBubble =
  "mr-auto max-w-[82%] rounded-[8px] rounded-bl-sm border border-line bg-paper px-4 py-3 text-sm leading-6 text-ink shadow-[0_1px_2px_rgba(13,31,58,0.04)]"
const noticeClass =
  "mx-auto max-w-[92%] rounded-full border border-line bg-paper px-3 py-1 text-center text-[11px] leading-5 text-mute"

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

const bubbleClass = (line: TranscriptLine, selfRole: TranscriptSelfRole) => {
  if (isCenteredNotice(line)) {
    return noticeClass
  }
  if (line.role === selfRole) {
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
  return "Agent"
}

const hasSource = (line: TranscriptLine) => {
  if (line.system_reason === "policy_boundary") {
    return line.role === "bot" || line.role === "system"
  }
  if (line.role !== "bot") {
    return false
  }
  return Boolean(line.source_chunk_ids?.length || line.source_urls?.length)
}

const citationFromLine = (line: TranscriptLine): SourceCitation => ({
  source_urls: line.source_urls,
  display_locator: line.display_locator,
  source_title:
    line.system_reason === "policy_boundary"
      ? line.source_title || "company policy"
      : line.source_title,
})

const sourceLabel = (line: TranscriptLine) =>
  line.system_reason === "policy_boundary" ? "company policy" : "Source"

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
        <SourceHoverCard
          citation={citationFromLine(line)}
          describedBy={messageId}
          label={sourceLabel(line)}
        />
      ) : null}
    </div>
  )
}

const TypingNotice = () => (
  <p className="text-mute flex items-center gap-2 px-1 text-xs" aria-live="polite">
    <span className="bg-steel size-1.5 rounded-full" />
    Agent is typing…
  </p>
)

const isEmptyTranscript = (
  lines: TranscriptLine[],
  typing: boolean,
  notice: string | undefined,
  logLabel: string | undefined,
) => lines.length === 0 && !typing && notice === undefined && logLabel === undefined

const transcriptSurface = (muted: boolean) => (muted ? "bg-ice-2" : "bg-[#FAFBFD]")

const TranscriptContent = ({
  lines,
  typing,
  notice,
  selfRole,
  latestRef,
}: {
  lines: TranscriptLine[]
  typing: boolean
  notice?: string
  selfRole: TranscriptSelfRole
  latestRef: ReturnType<typeof useAutoFollow>
}) => (
  <>
    {lines.map((line) => (
      <TranscriptRow key={line.id} line={line} selfRole={selfRole} />
    ))}
    {notice === undefined ? null : <p className={`${noticeClass} widget-bubble`}>{notice}</p>}
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
}: TranscriptProps) => {
  const latestRef = useAutoFollow(autoFollow, lines.at(-1)?.id)
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
      />
    </div>
  )
}
