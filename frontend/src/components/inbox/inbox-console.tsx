"use client"

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
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col lg:overflow-hidden">
      <div id="main-content" className="flex min-h-0 min-w-0 flex-1 flex-col">
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
              agentName={inbox.live.assigned?.display_name ?? null}
              lines={inbox.live.lines}
              hasOlder={detail.has_older === true}
              loadingOlder={inbox.loadingOlder}
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
              onLoadOlder={inbox.handleLoadOlder}
            />
          ) : (
            <EmptyTranscript loading={inbox.selectedId !== null} />
          )}
          {detail ? <VisitorRail key={detail.id} detail={detail} /> : null}
        </div>
      </div>
    </div>
  )
}

const EmptyTranscript = ({ loading }: { loading: boolean }) => {
  return (
    <section
      className="bg-ice flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center px-8"
      aria-busy={loading}
    >
      <h1 className="text-navy heading text-base">
        {loading ? "Opening conversation…" : "Select a conversation"}
      </h1>
      <p className="text-mute mt-2 max-w-xs text-center text-sm leading-6">
        {loading
          ? "Loading the latest transcript and visitor context."
          : "Choose a chat from Needs Attention to review its transcript and visitor context."}
      </p>
    </section>
  )
}

export type { InboxFilter, InboxListItem }
