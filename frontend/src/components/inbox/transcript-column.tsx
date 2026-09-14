"use client"

import { AgentComposer } from "./agent-composer"
import { HandoffCard } from "./handoff-card"
import { TranscriptPane } from "./transcript-pane"
import type { CannedReply } from "./types"
import type { useInboxLive } from "./use-inbox-live"

type TranscriptColumnProps = {
  visitorName: string
  siteName: string
  closed: boolean
  showJoin: boolean
  showMarkContacted: boolean
  showTransfer: boolean
  joinPending: boolean
  mine: boolean
  joinedBy: string | null
  lines: ReturnType<typeof useInboxLive>["live"]["lines"]
  composerEnabled: boolean
  canned: CannedReply[]
  inputId: string
  conversationId: string
  escalationReason: string | null
  isAdmin: boolean
  onJoin: () => void
  onMarkContacted: () => void
  onEnd: () => void
  onTransfer: () => void
  onSend: (body: string) => void
}

const TranscriptHeader = ({
  visitorName,
  siteName,
  closed,
}: Pick<TranscriptColumnProps, "visitorName" | "siteName" | "closed">) => (
  <div className="flex min-w-0 items-center gap-3">
    <span className="bg-ice-2 text-steel flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-bold">
      {visitorName.slice(0, 1).toUpperCase()}
    </span>
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-2">
        <h1 className="text-navy truncate text-sm font-extrabold">{visitorName}</h1>
        {closed ? (
          <span className="bg-ice-2 text-mute shrink-0 rounded-[8px] px-2 py-0.5 text-[10px] font-bold tracking-[0.08em] uppercase">
            Closed
          </span>
        ) : null}
      </div>
      <p className="text-mute mt-0.5 flex items-center gap-1.5 truncate text-xs">
        <span className="size-1.5 rounded-full bg-[#67B587]" />
        {siteName}
      </p>
    </div>
  </div>
)

const TranscriptActions = ({
  showJoin,
  showMarkContacted,
  showTransfer,
  joinPending,
  mine,
  conversationId,
  escalationReason,
  isAdmin,
  onJoin,
  onMarkContacted,
  onEnd,
  onTransfer,
}: Pick<
  TranscriptColumnProps,
  | "showJoin"
  | "showMarkContacted"
  | "showTransfer"
  | "joinPending"
  | "mine"
  | "conversationId"
  | "escalationReason"
  | "isAdmin"
  | "onJoin"
  | "onMarkContacted"
  | "onEnd"
  | "onTransfer"
>) => (
  <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
    {escalationReason ? (
      <HandoffCard key={conversationId} conversationId={conversationId} isAdmin={isAdmin} />
    ) : null}
    {showJoin ? (
      <button
        type="button"
        aria-busy={joinPending}
        disabled={joinPending}
        onClick={onJoin}
        className="bg-ember hover:bg-ember-mid disabled:bg-ember-soft focus-visible:ring-steel dark:text-navy-deep rounded-[8px] px-4 py-2.5 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
      >
        Join this chat
      </button>
    ) : null}
    {showMarkContacted ? (
      <button
        type="button"
        onClick={onMarkContacted}
        className="bg-steel hover:bg-navy focus-visible:ring-steel dark:text-navy-deep rounded-[8px] px-4 py-2.5 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
      >
        Mark contacted
      </button>
    ) : null}
    {mine ? (
      <>
        {showTransfer ? (
          <button
            type="button"
            onClick={onTransfer}
            className="border-line text-ink hover:bg-ice-2 focus-visible:ring-steel rounded-[8px] border px-4 py-2.5 text-sm font-bold focus-visible:ring-2 focus-visible:outline-none"
          >
            Transfer to assistant
          </button>
        ) : null}
        <button
          type="button"
          onClick={onEnd}
          className="border-line text-ink hover:bg-ice-2 focus-visible:ring-steel rounded-[8px] border px-4 py-2.5 text-sm font-bold focus-visible:ring-2 focus-visible:outline-none"
        >
          End chat
        </button>
      </>
    ) : null}
  </div>
)

export const TranscriptColumn = (props: TranscriptColumnProps) => {
  const {
    visitorName,
    siteName,
    closed,
    showJoin,
    showMarkContacted,
    composerEnabled,
    canned,
    inputId,
    lines,
    onSend,
  } = props

  return (
    <section className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="border-line/70 bg-paper flex shrink-0 items-center justify-between gap-3 border-b px-5 py-4">
        <TranscriptHeader visitorName={visitorName} siteName={siteName} closed={closed} />
        <TranscriptActions {...props} />
      </div>
      {props.joinedBy ? (
        <p className="border-line/70 text-mute bg-ice-2 shrink-0 border-b px-5 py-2.5 text-xs">
          Joined by {props.joinedBy}
        </p>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col">
        <TranscriptPane lines={lines} muted={closed} />
      </div>
      {showJoin && !composerEnabled && !closed ? (
        <p className="text-mute shrink-0 px-4 pt-2 text-xs">
          Join this chat to reply as a specialist.
        </p>
      ) : null}
      {showMarkContacted ? (
        <p className="text-mute shrink-0 px-4 pt-2 text-xs">
          Callback. Mark contacted when you have reached this visitor.
        </p>
      ) : null}
      <AgentComposer
        disabled={!composerEnabled || closed}
        closed={closed}
        canned={canned}
        inputId={inputId}
        onSend={onSend}
      />
    </section>
  )
}
