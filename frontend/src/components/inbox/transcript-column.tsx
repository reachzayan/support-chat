"use client"

import { ArrowLeftRight, CheckCircle2, LogOut, UserPlus } from "lucide-react"
import { motion } from "motion/react"
import { useMemo } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

import { AgentComposer } from "./agent-composer"
import { HandoffCard } from "./handoff-card"
import { HotGapBadge } from "./hot-gap-badge"
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
  agentName: string | null
  lines: ReturnType<typeof useInboxLive>["live"]["lines"]
  hasOlder: boolean
  loadingOlder: boolean
  composerEnabled: boolean
  canned: CannedReply[]
  inputId: string
  conversationId: string
  visitorEmail: string | null
  staffName: string
  staffEmail: string
  escalationReason: string | null
  isAdmin: boolean
  onJoin: () => void
  onMarkContacted: () => void
  onEnd: () => void
  onTransfer: () => void
  onSend: (body: string) => boolean
  onLoadOlder: () => void
}

const TAP_SCALE = { scale: 0.96 }
const BANNER_INITIAL = { opacity: 0, height: 0 }
const BANNER_ANIMATE = { opacity: 1, height: "auto" }

const avatarClass = "bg-ice-2 text-steel"

const MotionButton = motion.create(Button)

const META_PILL =
  "bg-ice-2 text-mute inline-flex shrink-0 items-center rounded-full px-2 py-1 text-[10px] font-bold"

const TranscriptHeader = ({
  visitorName,
  siteName,
  closed,
}: Pick<TranscriptColumnProps, "visitorName" | "siteName" | "closed">) => (
  <div className="flex min-w-0 items-center gap-3">
    <span
      className={`${avatarClass} flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold`}
    >
      {visitorName.slice(0, 1).toUpperCase()}
    </span>
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-2">
        <h1 className="text-navy heading truncate text-sm">{visitorName}</h1>
        {closed ? <span className={`${META_PILL} tracking-[0.08em] uppercase`}>Closed</span> : null}
      </div>
      <p className="text-mute mt-0.5 flex items-center gap-1.5 truncate text-xs">
        <span className="size-1.5 rounded-full bg-[#67B587]" />
        {siteName}
      </p>
    </div>
  </div>
)

const toolbarButtonBase =
  "focus-visible:ring-steel inline-flex h-9 items-center gap-1.5 px-3.5 text-[13px] font-bold leading-none focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"

const JoinButton = ({
  joinPending,
  onJoin,
}: Pick<TranscriptColumnProps, "joinPending" | "onJoin">) => (
  <MotionButton
    type="button"
    variant="default"
    size="lg"
    aria-busy={joinPending}
    disabled={joinPending}
    onClick={onJoin}
    whileTap={TAP_SCALE}
    className={`${toolbarButtonBase} shadow-[0_2px_8px_rgba(196,85,22,0.25)]`}
  >
    {joinPending ? (
      <Spinner data-icon="inline-start" />
    ) : (
      <UserPlus aria-hidden="true" className="size-3.5" strokeWidth={2.4} />
    )}
    {joinPending ? "Joining…" : "Join this chat"}
  </MotionButton>
)

const MarkContactedButton = ({
  onMarkContacted,
}: Pick<TranscriptColumnProps, "onMarkContacted">) => (
  <MotionButton
    type="button"
    variant="ghost"
    onClick={onMarkContacted}
    whileTap={TAP_SCALE}
    className={`${toolbarButtonBase} bg-steel hover:bg-navy text-white hover:text-white`}
  >
    <CheckCircle2 aria-hidden="true" className="size-3.5" strokeWidth={2.4} />
    Mark contacted
  </MotionButton>
)

const MineActions = ({
  showTransfer,
  onTransfer,
  onEnd,
}: Pick<TranscriptColumnProps, "showTransfer" | "onTransfer" | "onEnd">) => (
  <>
    {showTransfer ? (
      <MotionButton
        type="button"
        variant="ghost"
        onClick={onTransfer}
        whileTap={TAP_SCALE}
        className={`${toolbarButtonBase} border-line text-ink hover:bg-ice-2 border`}
      >
        <ArrowLeftRight aria-hidden="true" className="size-3.5" strokeWidth={2.2} />
        Transfer to assistant
      </MotionButton>
    ) : null}
    <MotionButton
      type="button"
      variant="ghost"
      onClick={onEnd}
      whileTap={TAP_SCALE}
      className={`${toolbarButtonBase} border-line text-ink hover:bg-ice-2 border`}
    >
      <LogOut aria-hidden="true" className="size-3.5" strokeWidth={2.2} />
      End chat
    </MotionButton>
  </>
)

const TranscriptActions = (
  props: Pick<
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
  >,
) => (
  <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
    <HotGapBadge key={props.conversationId} conversationId={props.conversationId} />
    {props.escalationReason ? (
      <HandoffCard
        key={props.conversationId}
        conversationId={props.conversationId}
        isAdmin={props.isAdmin}
      />
    ) : null}
    {props.showJoin ? <JoinButton joinPending={props.joinPending} onJoin={props.onJoin} /> : null}
    {props.showMarkContacted ? (
      <MarkContactedButton onMarkContacted={props.onMarkContacted} />
    ) : null}
    {props.mine ? (
      <MineActions
        showTransfer={props.showTransfer}
        onTransfer={props.onTransfer}
        onEnd={props.onEnd}
      />
    ) : null}
  </div>
)

const JoinedByBanner = ({ joinedBy }: { joinedBy: string }) => (
  <motion.p
    initial={BANNER_INITIAL}
    animate={BANNER_ANIMATE}
    className="border-line text-mute bg-ice-2 shrink-0 overflow-hidden border-b px-5 py-2.5 text-xs"
  >
    Joined by {joinedBy}
  </motion.p>
)

export const TranscriptColumn = (props: TranscriptColumnProps) => {
  const {
    visitorName,
    siteName,
    closed,
    showMarkContacted,
    composerEnabled,
    canned,
    inputId,
    lines,
    onSend,
  } = props
  const cannedVariables = useMemo(
    () => ({
      customerName: visitorName === "Unknown visitor" ? "" : visitorName,
      customerEmail: props.visitorEmail,
      agentName: props.staffName,
      agentEmail: props.staffEmail,
    }),
    [props.staffEmail, props.staffName, props.visitorEmail, visitorName],
  )

  return (
    <section className="bg-paper flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="border-line bg-paper flex h-16 shrink-0 items-center justify-between gap-3 border-b px-5">
        <TranscriptHeader visitorName={visitorName} siteName={siteName} closed={closed} />
        <TranscriptActions {...props} />
      </div>
      {props.joinedBy ? <JoinedByBanner joinedBy={props.joinedBy} /> : null}
      {props.hasOlder ? (
        <div className="border-line bg-paper flex shrink-0 justify-center border-b px-4 py-2">
          <Button
            type="button"
            variant="ghost"
            disabled={props.loadingOlder}
            aria-busy={props.loadingOlder}
            onClick={props.onLoadOlder}
            className="text-steel focus-visible:ring-steel hover:bg-ice-2 px-3 py-1 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.loadingOlder ? <Spinner data-icon="inline-start" /> : null}
            {props.loadingOlder ? "Loading older messages…" : "Load older messages"}
          </Button>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col">
        <TranscriptPane
          lines={lines}
          muted={closed}
          closed={closed}
          companyName={siteName}
          agentName={props.agentName}
        />
      </div>
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
        variables={cannedVariables}
        onSend={onSend}
      />
    </section>
  )
}
