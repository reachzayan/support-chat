"use client"

import { ArrowLeft } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { RetryError } from "@/components/admin/retry-error"
import { useConversationNotifications } from "@/components/notifications/notifications-context"
import { Button } from "@/components/ui/button"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { useIsMobile } from "@/hooks/use-mobile"
import type { StaffUser } from "@/lib/auth-client"

import { ConversationList } from "./conversation-list"
import { TranscriptColumn } from "./transcript-column"
import type { ConversationDetail, InboxFilter, InboxListItem } from "./types"
import { useInboxLive } from "./use-inbox-live"
import { VisitorRail } from "./visitor-rail"

type InboxConsoleProps = {
  user: StaffUser
  initialConversationId?: string | null
}

export const InboxConsole = ({ user, initialConversationId }: InboxConsoleProps) => {
  const inbox = useInboxLive(user.id)
  const select = inbox.handleSelect
  const clear = inbox.clearSelection
  useEffect(() => {
    if (initialConversationId) select(initialConversationId)
    else if (initialConversationId === null) clear()
  }, [initialConversationId, select, clear])
  return <InboxShell user={user} inbox={inbox} />
}

type LiveSlice = ReturnType<typeof useInboxLive>["live"]

const isAssignedTo = (live: LiveSlice, userId: string) => {
  return live.chatState === "human" && live.assigned?.id === userId
}

const canOfferJoin = (live: LiveSlice, mine: boolean, detail: ConversationDetail) => {
  if (mine) {
    return false
  }
  if (!detail.human_enabled) {
    return false
  }
  return live.chatState === "queued" || live.chatState === "bot" || live.joinPending
}

const canMarkContacted = (live: LiveSlice, detail: ConversationDetail) => {
  return live.chatState === "queued" && detail.attention_needed && !detail.human_enabled
}

const otherAgentName = (live: LiveSlice, mine: boolean) => {
  if (mine || live.chatState !== "human") {
    return null
  }
  return live.winnerName
}

type InboxShellProps = {
  user: StaffUser
  inbox: ReturnType<typeof useInboxLive>
}

const InboxShell = ({ user, inbox }: InboxShellProps) => {
  const compact = useIsMobile(1280)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const openDetails = useCallback(() => setDetailsOpen(true), [])
  const detail = inbox.live.detail
  return (
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col lg:overflow-hidden">
      <ConversationReadObserver detail={detail} selectedId={inbox.selectedId} />
      <div id="main-content" className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col xl:flex-row">
          <div
            hidden={compact && inbox.selectedId !== null}
            className={
              compact && inbox.selectedId !== null
                ? "hidden"
                : "flex min-h-0 flex-1 flex-col xl:contents"
            }
          >
            <ConversationList
              filter={inbox.filter}
              siteId={inbox.siteId}
              sites={inbox.sites}
              items={inbox.items}
              selectedId={inbox.selectedId}
              nextCursor={inbox.nextCursor}
              counts={inbox.counts}
              loadError={inbox.loadError}
              onFilter={inbox.setFilter}
              onSite={inbox.setSite}
              onSelect={inbox.handleSelect}
              onLoadMore={inbox.handleLoadMore}
              onRetryLoad={inbox.handleRetryLoad}
            />
          </div>
          {compact && inbox.selectedId !== null && !detail ? (
            <div className="border-line bg-paper flex shrink-0 items-center justify-between border-b px-2 py-1">
              <Button variant="ghost" className="min-h-11" onClick={inbox.clearSelection}>
                <ArrowLeft aria-hidden="true" className="size-4" /> Back to conversations
              </Button>
            </div>
          ) : null}
          {!compact || inbox.selectedId !== null ? (
            <SelectedConversation
              user={user}
              inbox={inbox}
              compact={compact}
              onVisitorDetails={openDetails}
              detailsOpen={detailsOpen}
            />
          ) : null}
          <VisitorContext
            detail={detail}
            compact={compact}
            open={detailsOpen}
            onOpenChange={setDetailsOpen}
          />
        </div>
      </div>
    </div>
  )
}

const ConversationReadObserver = ({
  detail,
  selectedId,
}: {
  detail: ConversationDetail | null
  selectedId: string | null
}) => {
  useConversationNotifications(detail?.id === selectedId ? selectedId : null)
  return null
}

const VisitorContext = ({
  detail,
  compact,
  open,
  onOpenChange,
}: {
  detail: ConversationDetail | null
  compact: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
}) => {
  const mobile = useIsMobile()
  if (!detail) return null
  if (!compact) return <VisitorRail key={detail.id} detail={detail} />
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      swipeDirection={mobile ? "down" : "right"}
      showSwipeHandle={mobile}
    >
      <DrawerContent
        className={
          mobile ? "h-[85dvh] w-full max-w-none gap-0 rounded-t-3xl" : "w-full max-w-sm gap-0"
        }
      >
        <DrawerHeader className={mobile ? "min-h-0 pt-0 pb-3" : undefined}>
          <DrawerTitle>Visitor details</DrawerTitle>
          <DrawerDescription className="truncate">
            {detail.visitor.name ?? "Unknown visitor"} · {detail.site_name}
          </DrawerDescription>
        </DrawerHeader>
        <div className="flex min-h-0 flex-1 [&>aside]:w-full [&>aside]:flex-1 [&>aside]:border-l-0">
          <VisitorRail key={detail.id} detail={detail} showHeader={false} />
        </div>
      </DrawerContent>
    </Drawer>
  )
}

const SelectedConversation = ({
  user,
  inbox,
  compact,
  onVisitorDetails,
  detailsOpen,
}: InboxShellProps & {
  compact: boolean
  onVisitorDetails: () => void
  detailsOpen: boolean
}) => {
  const detail = inbox.live.detail
  const userId = user.id
  const isAdmin = user.is_admin
  const mine = isAssignedTo(inbox.live, userId)
  if (!detail)
    return (
      <EmptyTranscript
        loading={inbox.selectedId !== null}
        error={inbox.detailError}
        onRetry={inbox.handleRetryDetail}
      />
    )
  return (
    <TranscriptColumn
      onBack={compact ? inbox.clearSelection : undefined}
      onVisitorDetails={compact ? onVisitorDetails : undefined}
      detailsOpen={detailsOpen}
      visitorName={detail.visitor.name ?? "Unknown visitor"}
      siteName={detail.site_name}
      closed={inbox.live.chatState === "closed"}
      showJoin={canOfferJoin(inbox.live, mine, detail)}
      showMarkContacted={canMarkContacted(inbox.live, detail)}
      showTransfer={mine && detail.bot_enabled}
      joinPending={inbox.live.joinPending}
      mine={mine}
      joinedBy={otherAgentName(inbox.live, mine)}
      agentName={inbox.live.assigned?.display_name ?? null}
      lines={inbox.live.lines}
      hasOlder={detail.has_older === true}
      loadingOlder={inbox.loadingOlder}
      composerEnabled={mine}
      canned={inbox.canned}
      inputId={`inbox-message-${userId}`}
      conversationId={detail.id}
      visitorEmail={detail.visitor.email}
      staffName={user.display_name}
      staffEmail={user.email}
      escalationReason={detail.escalation_reason ?? null}
      isAdmin={isAdmin}
      onJoin={inbox.handleJoin}
      onMarkContacted={inbox.handleMarkContacted}
      onEnd={inbox.handleEnd}
      onTransfer={inbox.handleTransfer}
      onSend={inbox.handleSend}
      onLoadOlder={inbox.handleLoadOlder}
    />
  )
}

const EmptyTranscript = ({
  loading,
  error,
  onRetry,
}: {
  loading: boolean
  error: boolean
  onRetry: () => void
}) => {
  if (error && loading)
    return (
      <section className="flex flex-1 items-center justify-center p-6">
        <RetryError text="Could not open conversation." onRetry={onRetry} />
      </section>
    )
  if (loading) return <TranscriptSkeleton />
  return (
    <section className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center px-8">
      <h1 className="text-navy heading text-base">Select a conversation</h1>
      <p className="text-mute mt-2 max-w-xs text-center text-sm leading-6">
        Choose a chat from Needs Attention to review its transcript and visitor context.
      </p>
    </section>
  )
}

const SKELETON_BUBBLES = [
  "w-2/3 self-start",
  "w-1/2 self-end",
  "w-3/5 self-start",
  "w-2/5 self-end",
] as const

const TranscriptSkeleton = () => (
  <output
    aria-label="Opening conversation"
    aria-busy="true"
    className="bg-paper flex min-h-0 min-w-0 flex-1 flex-col"
  >
    <div className="border-line flex min-h-16 shrink-0 items-center gap-3 border-b px-4 lg:px-5">
      <span className="bg-ice-2 size-10 shrink-0 rounded-full motion-safe:animate-pulse" />
      <div className="flex flex-1 flex-col gap-2">
        <span className="bg-ice-2 h-3 w-32 rounded motion-safe:animate-pulse" />
        <span className="bg-ice-2 h-2.5 w-20 rounded motion-safe:animate-pulse" />
      </div>
    </div>
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-5" aria-hidden="true">
      {SKELETON_BUBBLES.map((width) => (
        <span
          key={width}
          className={`bg-ice-2 h-12 rounded-2xl motion-safe:animate-pulse ${width}`}
        />
      ))}
    </div>
    <h1 className="text-navy heading px-5 pb-6 text-center text-sm">Opening conversation…</h1>
  </output>
)

export type { InboxFilter, InboxListItem }
