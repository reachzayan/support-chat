"use client"

import { StaffHeader } from "@/components/admin/staff-nav"
import type { StaffUser } from "@/lib/auth-client"

import { ConversationList } from "./conversation-list"
import { TranscriptColumn } from "./transcript-column"
import type { ConversationDetail, InboxFilter, InboxListItem } from "./types"
import { useInboxLive } from "./use-inbox-live"
import { VisitorRail } from "./visitor-rail"

type InboxConsoleProps = {
  user: StaffUser
}

export const InboxConsole = ({ user }: InboxConsoleProps) => {
  const inbox = useInboxLive(user.id)
  return <InboxShell userId={user.id} isAdmin={user.is_admin} inbox={inbox} />
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
  userId: string
  isAdmin: boolean
  inbox: ReturnType<typeof useInboxLive>
}

const InboxShell = ({ userId, isAdmin, inbox }: InboxShellProps) => {
  const mine = isAssignedTo(inbox.live, userId)
  const detail = inbox.live.detail
  return (
    <div className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col lg:overflow-hidden">
      <div id="main-content" className="flex min-h-0 min-w-0 flex-1 flex-col">
        <StaffHeader
          eyebrow="Workspace / Inbox"
          title="Inbox"
          description="Keep visitor conversations moving, from the first question to specialist follow-up."
        />
        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <ConversationList
            filter={inbox.filter}
            items={inbox.items}
            selectedId={inbox.selectedId}
            nextCursor={inbox.nextCursor}
            counts={inbox.counts}
            onFilter={inbox.setFilter}
            onSelect={inbox.handleSelect}
            onLoadMore={inbox.handleLoadMore}
          />
          {detail ? (
            <TranscriptColumn
              visitorName={detail.visitor.name ?? "Unknown visitor"}
              siteName={detail.site_name}
              closed={inbox.live.chatState === "closed"}
              showJoin={canOfferJoin(inbox.live, mine, detail)}
              showMarkContacted={canMarkContacted(inbox.live, detail)}
              showTransfer={mine && detail.bot_enabled}
              joinPending={inbox.live.joinPending}
              mine={mine}
              joinedBy={otherAgentName(inbox.live, mine)}
              lines={inbox.live.lines}
              composerEnabled={mine}
              canned={inbox.canned}
              inputId={`inbox-message-${userId}`}
              conversationId={detail.id}
              escalationReason={detail.escalation_reason ?? null}
              isAdmin={isAdmin}
              onJoin={inbox.handleJoin}
              onMarkContacted={inbox.handleMarkContacted}
              onEnd={inbox.handleEnd}
              onTransfer={inbox.handleTransfer}
              onSend={inbox.handleSend}
            />
          ) : (
            <EmptyTranscript />
          )}
          {detail ? (
            <VisitorRail detail={detail} />
          ) : (
            <aside
              className="border-line bg-ice-2 hidden min-h-0 border-l lg:block lg:w-[300px] lg:shrink-0"
              aria-hidden="true"
            />
          )}
        </div>
      </div>
    </div>
  )
}

const EmptyTranscript = () => {
  return (
    <section className="bg-paper flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center px-8">
      <span className="border-line bg-ice-2 mb-4 flex size-12 items-center justify-center rounded-full border">
        <span className="bg-steel size-2.5 rounded-full" />
      </span>
      <p className="text-mute mb-2 text-[10px] font-bold tracking-[0.16em] uppercase">Inbox</p>
      <h1 className="text-navy text-base font-extrabold">Select a conversation</h1>
      <p className="text-mute mt-2 max-w-xs text-center text-sm leading-6">
        Choose a chat from the queue to review its transcript and visitor context.
      </p>
    </section>
  )
}

export type { InboxFilter, InboxListItem }
