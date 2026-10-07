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
  useMessageScroller,
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
  companyName?: string | null
  logLabel?: string
  autoFollow?: boolean
  muted?: boolean
  conversationState?: TranscriptConversationState | null
}

type FeedItem =
  | { kind: "day"; id: string; label: string }
  | { kind: "time"; id: string; dateTime: string; label: string }
  | { kind: "line"; line: TranscriptLine }

const IDLE_WARNING = "This chat will close in 1 minute. Send a message to keep active."
const IDLE_CLOSED = "This chat has been closed automatically."

const IDLE_WARN_MS = 4 * 60 * 1000
const IDLE_CLOSE_MS = 5 * 60 * 1000
const IDLE_TICK_MS = 15_000
const TIME_GAP_MS = 10 * 60 * 1000

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
  const body = line.body.trim()
  return (
    /^(this chat is closed|this chat was closed(?: by .+)?)\.?$/i.test(body) ||
    body === IDLE_CLOSED ||
    /^this chat has been closed automatically\.?$/i.test(body)
  )
}

export const isCenteredNotice = (line: TranscriptLine) => {
  if (line.role !== "system") {
    return false
  }
  const body = line.body.trim()
  return (
    isClosedNotice(line) ||
    /^(a human has joined)\.?$/i.test(body) ||
    /^you(?:'|’)re now chatting with .+\.?$/i.test(body) ||
    /^(this chat was reset by the visitor|this chat has been resumed)\.?$/i.test(body) ||
    /^this chat will close in 1 minute\. send a message to keep active\.?$/i.test(body)
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

const hasPersistedIdleWarning = (lines: TranscriptLine[]) =>
  lines.some(
    (line) =>
      line.role === "system" &&
      /^this chat will close in 1 minute\. send a message to keep active\.?$/i.test(
        line.body.trim(),
      ),
  )

const isIdleWarningDue = (
  conversationState: TranscriptConversationState | null | undefined,
  lines: TranscriptLine[],
  nowMs: number,
) => {
  if (conversationState !== "bot" && conversationState !== "human") {
    return false
  }
  if (hasPersistedIdleWarning(lines)) {
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

const isStaffLine = (line: TranscriptLine) =>
  line.role === "agent" ||
  line.role === "admin" ||
  line.role === "bot" ||
  (line.role === "system" && !isCenteredNotice(line))

const isSelfLine = (line: TranscriptLine, selfRole: TranscriptSelfRole) =>
  selfRole === "visitor" ? line.role === "visitor" : isStaffLine(line)

const firstName = (displayName: string) => displayName.trim().split(/\s+/)[0] || displayName

const companyLabel = (companyName: string | null | undefined) => {
  const name = companyName?.trim()
  return name ? name : null
}

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

const staffCompanyLabel = (
  line: TranscriptLine,
  agentName: string | null | undefined,
  companyName: string | null | undefined,
) => {
  const person = staffName(line, agentName)
  const company = companyLabel(companyName)
  if (person && company) {
    return `${firstName(person)} - ${company}`
  }
  if (person) {
    return firstName(person)
  }
  return company
}

const roleLabel = (
  line: TranscriptLine,
  selfRole: TranscriptSelfRole,
  agentName: string | null | undefined,
  companyName: string | null | undefined,
) => {
  if (isCenteredNotice(line)) {
    return null
  }
  if (line.role === "visitor") {
    return selfRole === "visitor" ? null : "Visitor"
  }
  if (line.role === "agent" || line.role === "admin") {
    return staffCompanyLabel(line, agentName, companyName)
  }
  return companyLabel(companyName)
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

const maybeDayItem = (
  line: TranscriptLine,
  day: string | null,
  lastDay: string | null,
  now: Date,
): FeedItem | null => {
  if (!day || day === lastDay || !line.created_at) {
    return null
  }
  const label = formatDayLabel(line.created_at, now)
  if (!label) {
    return null
  }
  return { kind: "day", id: `day-${day}`, label }
}

const maybeTimeItem = (
  line: TranscriptLine,
  date: Date | null,
  lastStampMs: number | null,
): FeedItem | null => {
  if (!date || !line.created_at || lastStampMs === null) {
    return null
  }
  if (date.getTime() - lastStampMs < TIME_GAP_MS) {
    return null
  }
  const label = formatMessageTime(line.created_at)
  if (!label) {
    return null
  }
  return { kind: "time", id: `time-${line.id}`, dateTime: line.created_at, label }
}

const buildFeed = (lines: TranscriptLine[], now: Date): FeedItem[] => {
  const showDays = shouldShowDayMarkers(lines, now)
  const items: FeedItem[] = []
  let lastDay: string | null = null
  let lastStampMs: number | null = null
  for (const line of lines) {
    const date = parseStamp(line.created_at)
    const day = date ? localDayKey(date) : null
    if (showDays) {
      const dayItem = maybeDayItem(line, day, lastDay, now)
      if (dayItem) {
        items.push(dayItem)
        lastDay = day
      }
    }
    const timeItem = maybeTimeItem(line, date, lastStampMs)
    if (timeItem) {
      items.push(timeItem)
    }
    if (date) {
      lastStampMs = date.getTime()
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
  companyName,
}: {
  line: TranscriptLine
  selfRole: TranscriptSelfRole
  agentName?: string | null
  companyName?: string | null
}) => {
  const label = roleLabel(line, selfRole, agentName, companyName)
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
  companyName,
}: {
  line: TranscriptLine
  selfRole: TranscriptSelfRole
  agentName?: string | null
  companyName?: string | null
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
      <TranscriptMessage
        line={line}
        selfRole={selfRole}
        agentName={agentName}
        companyName={companyName}
      />
    </AnimatedItem>
  )
}

const DayMarker = ({ id, label }: { id: string; label: string }) => (
  <AnimatedItem messageId={id}>
    <CenteredPill>{label}</CenteredPill>
  </AnimatedItem>
)

const GapTimestamp = ({ id, dateTime, label }: { id: string; dateTime: string; label: string }) => (
  <AnimatedItem messageId={id}>
    <time
      dateTime={dateTime}
      className="text-mute mx-auto block text-center text-[11px] font-normal"
    >
      {label}
    </time>
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
        <Marker render={<output />} className={centeredPillClass}>
          <MarkerContent className="text-center">{IDLE_WARNING}</MarkerContent>
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

const TranscriptFeedItem = ({
  item,
  selfRole,
  agentName,
  companyName,
}: {
  item: FeedItem
  selfRole: TranscriptSelfRole
  agentName?: string | null
  companyName?: string | null
}) => {
  if (item.kind === "day") {
    return <DayMarker id={item.id} label={item.label} />
  }
  if (item.kind === "time") {
    return <GapTimestamp id={item.id} dateTime={item.dateTime} label={item.label} />
  }
  return (
    <TranscriptRow
      line={item.line}
      selfRole={selfRole}
      agentName={agentName}
      companyName={companyName}
    />
  )
}

const feedItemKey = (item: FeedItem) => (item.kind === "line" ? String(item.line.id) : item.id)
const latestMessageId = (lines: TranscriptLine[]) => lines.at(-1)?.id

const FollowLatestMessage = ({ enabled, latestId }: { enabled: boolean; latestId?: number }) => {
  const { scrollToEnd } = useMessageScroller()
  useEffect(() => {
    if (!enabled || latestId === undefined) return
    // Let the prebuilt scroller measure the committed rows before following the new message.
    const frame = window.requestAnimationFrame(() => scrollToEnd({ behavior: "auto" }))
    return () => window.cancelAnimationFrame(frame)
  }, [enabled, latestId, scrollToEnd])
  return null
}

export const Transcript = ({
  lines,
  typing = false,
  notice,
  selfRole = "visitor",
  agentName = null,
  companyName,
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
            aria-live="polite"
            aria-relevant="additions"
            aria-busy={typing || undefined}
            className="gap-5 px-5 pt-5 pb-14"
          >
            {feed.map((item) => (
              <TranscriptFeedItem
                key={feedItemKey(item)}
                item={item}
                selfRole={selfRole}
                agentName={agentName}
                companyName={companyName}
              />
            ))}
            <TranscriptExtras
              notice={notice}
              showIdleWarning={showIdleWarning}
              typing={typing}
              typingLabel={typingCopy(conversationState, agentName)}
            />
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <FollowLatestMessage enabled={autoFollow} latestId={latestMessageId(lines)} />
        <MessageScrollerButton
          variant="outline"
          className="border-steel/15 bg-ice-2 text-navy hover:!text-navy shadow-[0_6px_16px_rgba(36,86,160,0.12)] hover:!bg-[#e6eefc]"
        />
      </MessageScroller>
    </MessageScrollerProvider>
  )
}
