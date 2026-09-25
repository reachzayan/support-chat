/* oxlint-disable react-perf/jsx-no-jsx-as-prop */

"use client"

import { motion, useReducedMotion } from "motion/react"
import { useEffect, useState, type ReactNode } from "react"

import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { Message, MessageContent, MessageFooter, MessageHeader } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { Spinner } from "@/components/ui/spinner"

import { SourceHoverCard, type SourceCitation } from "./source-hovercard"

export type TranscriptAuthor = {
  id: string
  display_name: string
}

export type TranscriptLine = {
  id: number
  role: string
  body: string
  created_at?: string | null
  author_user?: TranscriptAuthor | null
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
  agentName?: string | null
  logLabel?: string
  autoFollow?: boolean
  muted?: boolean
  conversationState?: TranscriptConversationState | null
}

type FeedItem = { kind: "day"; id: string; label: string } | { kind: "line"; line: TranscriptLine }

const IDLE_WARNING = "This chat will be closed in one minute. Send any message to keep active."

const IDLE_WARN_MS = 4 * 60 * 1000
const IDLE_CLOSE_MS = 5 * 60 * 1000
const IDLE_TICK_MS = 15_000

const ENTER = { opacity: 0, y: 16 } as const
const SETTLED = { opacity: 1, y: 0 } as const
const ENTER_TRANSITION = { duration: 0.18, ease: [0.22, 1, 0.36, 1] } as const
const centeredPillClass =
  "mx-auto w-fit max-w-[92%] rounded-full bg-ice-2 px-3 py-1 text-center text-[11px] leading-5 text-mute"

const MotionScrollerItem = motion.create(MessageScrollerItem)

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
    /^you(?:'|’)re now chatting with .+\.?$/i.test(line.body.trim()) ||
    /^(this chat was reset by the visitor|this chat has been resumed)\.?$/i.test(line.body.trim())
  )
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

const isSelfLine = (line: TranscriptLine, selfRole: TranscriptSelfRole) =>
  line.role === selfRole ||
  (selfRole === "agent" && (line.role === "agent" || line.role === "admin" || line.role === "bot"))

const staffName = (line: TranscriptLine, agentName: string | null | undefined) => {
  const authored = line.author_user?.display_name?.trim()
  if (authored) {
    return authored
  }
  const assigned = agentName?.trim()
  if (assigned) {
    return assigned
  }
  return null
}

const roleLabel = (
  line: TranscriptLine,
  selfRole: TranscriptSelfRole,
  agentName: string | null | undefined,
) => {
  if (isCenteredNotice(line) || line.role === selfRole) {
    return null
  }
  if (line.role === "visitor") {
    return "Visitor"
  }
  if (line.role === "bot") {
    return "Assistant"
  }
  if (line.role === "agent" || line.role === "admin") {
    return staffName(line, agentName) ?? (line.role === "admin" ? "Admin" : "Agent")
  }
  return "Agent"
}

const parseStamp = (value: string | null | undefined) => {
  if (!value) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date
}

const localDayKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`

const formatMessageTime = (value: string | null | undefined) => {
  const date = parseStamp(value)
  if (!date) {
    return null
  }
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

const formatDayLabel = (value: string, now: Date) => {
  const date = parseStamp(value)
  if (!date) {
    return null
  }
  const key = localDayKey(date)
  if (key === localDayKey(now)) {
    return "Today"
  }
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (key === localDayKey(yesterday)) {
    return "Yesterday"
  }
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  })
}

const shouldShowDayMarkers = (lines: TranscriptLine[], now: Date) => {
  const days = new Set<string>()
  for (const line of lines) {
    const date = parseStamp(line.created_at)
    if (date) {
      days.add(localDayKey(date))
    }
  }
  if (days.size === 0) {
    return false
  }
  if (days.size > 1) {
    return true
  }
  return !days.has(localDayKey(now))
}

const buildFeed = (lines: TranscriptLine[], now: Date): FeedItem[] => {
  const showDays = shouldShowDayMarkers(lines, now)
  const items: FeedItem[] = []
  let lastDay: string | null = null
  for (const line of lines) {
    const date = parseStamp(line.created_at)
    const day = date ? localDayKey(date) : null
    if (showDays && day && day !== lastDay && line.created_at) {
      const label = formatDayLabel(line.created_at, now)
      if (label) {
        items.push({ kind: "day", id: `day-${day}`, label })
      }
      lastDay = day
    }
    items.push({ kind: "line", line })
  }
  return items
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

const isEmptyTranscript = (
  lines: TranscriptLine[],
  typing: boolean,
  notice: string | undefined,
  logLabel: string | undefined,
) => lines.length === 0 && !typing && notice === undefined && logLabel === undefined

const transcriptSurface = () => "bg-paper"

const AnimatedItem = ({
  messageId,
  scrollAnchor,
  children,
}: {
  messageId: string
  scrollAnchor?: boolean
  children: ReactNode
}) => {
  const reducedMotion = useReducedMotion()
  return (
    <MotionScrollerItem
      messageId={messageId}
      scrollAnchor={scrollAnchor}
      initial={reducedMotion ? false : ENTER}
      animate={SETTLED}
      transition={ENTER_TRANSITION}
    >
      {children}
    </MotionScrollerItem>
  )
}

const TranscriptAttachments = ({ line }: { line: TranscriptLine }) => {
  if (!hasSource(line)) {
    return null
  }
  const messageId = `transcript-msg-${line.id}`
  return (
    <div className="flex w-full min-w-0 flex-col gap-1.5">
      {citationsFromLine(line).map((citation, index) => {
        const href = citation.source_urls?.[0]?.trim() || ""
        const title = citation.source_title?.trim() || ""
        const cited = citation.cited_text?.trim().slice(0, 48) || ""
        return (
          <SourceHoverCard
            key={`${href}|${title}|${cited}`}
            citation={citation}
            describedBy={messageId}
            label={title || `Source ${index + 1}`}
          />
        )
      })}
    </div>
  )
}

const TranscriptTime = ({ line }: { line: TranscriptLine }) => {
  const timeLabel = formatMessageTime(line.created_at)
  if (!timeLabel || !line.created_at) {
    return null
  }
  return (
    <MessageFooter>
      <time dateTime={line.created_at} className="text-mute text-[11px] font-normal">
        {timeLabel}
      </time>
    </MessageFooter>
  )
}

const TranscriptMessage = ({
  line,
  selfRole,
  agentName,
}: {
  line: TranscriptLine
  selfRole: TranscriptSelfRole
  agentName?: string | null
}) => {
  const label = roleLabel(line, selfRole, agentName)
  const align = isSelfLine(line, selfRole) ? "end" : "start"
  const messageId = `transcript-msg-${line.id}`
  const outgoing = align === "end"
  return (
    <Message align={align}>
      <MessageContent>
        {label ? <MessageHeader>{label}</MessageHeader> : null}
        <Bubble
          variant={outgoing ? "steel" : "secondary"}
          align={align}
          className={
            outgoing ? "max-w-[min(80%,20rem)] min-w-[5.5rem]" : "w-full max-w-[min(100%,24rem)]"
          }
        >
          <BubbleContent id={messageId} className="whitespace-pre-wrap">
            {line.body}
          </BubbleContent>
          <TranscriptAttachments line={line} />
        </Bubble>
        <TranscriptTime line={line} />
      </MessageContent>
    </Message>
  )
}

const CenteredPill = ({ children }: { children: ReactNode }) => (
  <Marker className={centeredPillClass}>
    <MarkerContent className="text-center">{children}</MarkerContent>
  </Marker>
)

const TranscriptRow = ({
  line,
  selfRole,
  agentName,
}: {
  line: TranscriptLine
  selfRole: TranscriptSelfRole
  agentName?: string | null
}) => {
  if (isCenteredNotice(line)) {
    return (
      <AnimatedItem messageId={String(line.id)}>
        <CenteredPill>{line.body}</CenteredPill>
      </AnimatedItem>
    )
  }
  return (
    <AnimatedItem messageId={String(line.id)} scrollAnchor={line.role === "visitor"}>
      <TranscriptMessage line={line} selfRole={selfRole} agentName={agentName} />
    </AnimatedItem>
  )
}

const DayMarker = ({ id, label }: { id: string; label: string }) => (
  <AnimatedItem messageId={id}>
    <CenteredPill>{label}</CenteredPill>
  </AnimatedItem>
)

const typingCopy = (
  conversationState: TranscriptConversationState | null,
  agentName?: string | null,
) => {
  if (conversationState === "human") {
    const name = agentName?.trim()
    if (name) {
      return `${name} is typing…`
    }
  }
  return "Assistant is typing…"
}

const TranscriptExtras = ({
  notice,
  showIdleWarning,
  typing,
  typingLabel,
}: {
  notice?: string
  showIdleWarning: boolean
  typing: boolean
  typingLabel: string
}) => (
  <>
    {notice === undefined ? null : (
      <AnimatedItem messageId="notice">
        <CenteredPill>{notice}</CenteredPill>
      </AnimatedItem>
    )}
    {showIdleWarning ? (
      <AnimatedItem messageId="idle-warning">
        <Marker render={<output />}>
          <MarkerContent>{IDLE_WARNING}</MarkerContent>
        </Marker>
      </AnimatedItem>
    ) : null}
    {typing ? (
      <AnimatedItem messageId="typing">
        <Marker render={<output />}>
          <MarkerIcon>
            <Spinner />
          </MarkerIcon>
          <MarkerContent>{typingLabel}</MarkerContent>
        </Marker>
      </AnimatedItem>
    ) : null}
  </>
)

export const Transcript = ({
  lines,
  typing = false,
  notice,
  selfRole = "visitor",
  agentName = null,
  logLabel,
  autoFollow = false,
  muted = false,
  conversationState = null,
}: TranscriptProps) => {
  const showIdleWarning = useIdleWarning(conversationState, lines)
  const surface = transcriptSurface()
  if (isEmptyTranscript(lines, typing, notice, logLabel)) {
    return <div aria-live="polite" className={`min-h-0 flex-1 ${surface}`} />
  }
  const feed = buildFeed(lines, new Date())
  return (
    <MessageScrollerProvider autoScroll={autoFollow} defaultScrollPosition="end">
      <MessageScroller className={`min-h-0 flex-1 ${surface} ${muted ? "opacity-90" : ""}`}>
        <MessageScrollerViewport>
          <MessageScrollerContent
            aria-label={logLabel}
            aria-busy={typing || undefined}
            className="gap-5 px-5 pt-5 pb-14"
          >
            {feed.map((item) =>
              item.kind === "day" ? (
                <DayMarker key={item.id} id={item.id} label={item.label} />
              ) : (
                <TranscriptRow
                  key={item.line.id}
                  line={item.line}
                  selfRole={selfRole}
                  agentName={agentName}
                />
              ),
            )}
            <TranscriptExtras
              notice={notice}
              showIdleWarning={showIdleWarning}
              typing={typing}
              typingLabel={typingCopy(conversationState, agentName)}
            />
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton
          variant="outline"
          className="border-steel/15 bg-ice-2 text-navy hover:!text-navy shadow-[0_6px_16px_rgba(36,86,160,0.12)] hover:!bg-[#e6eefc]"
        />
      </MessageScroller>
    </MessageScrollerProvider>
  )
}
