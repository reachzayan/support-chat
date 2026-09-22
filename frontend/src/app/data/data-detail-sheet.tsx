"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import { Transcript } from "@/app/widget/transcript"
import { fetchInboxDetailPage, mergeInboxMessages } from "@/components/inbox/inbox-api"
import type { ConversationDetail, InboxMessage } from "@/components/inbox/types"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"

import { blank, STATE_LABEL, type SubmissionRow } from "./data-shared"

const TranscriptPane = ({
  loading,
  error,
  lines,
  hasOlder,
  loadingOlder,
  onLoadOlder,
}: {
  loading: boolean
  error: boolean
  lines: InboxMessage[]
  hasOlder: boolean
  loadingOlder: boolean
  onLoadOlder: () => void
}) => {
  if (loading) {
    return <p className="text-mute px-5 py-6 text-sm">Loading transcript…</p>
  }
  if (error) {
    return <p className="text-mute px-5 py-6 text-sm">Transcript is not available for this chat.</p>
  }
  if (lines.length === 0) {
    return <p className="text-mute px-5 py-6 text-sm">No transcript yet.</p>
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {hasOlder ? (
        <div className="border-line bg-paper flex shrink-0 justify-center border-b px-4 py-2">
          <button
            type="button"
            disabled={loadingOlder}
            aria-busy={loadingOlder}
            onClick={onLoadOlder}
            className="text-steel focus-visible:ring-steel hover:bg-ice-2 rounded-full px-3 py-1 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadingOlder ? "Loading older messages…" : "Load older messages"}
          </button>
        </div>
      ) : null}
      <Transcript lines={lines} selfRole="agent" logLabel="Transcript" />
    </div>
  )
}

const useSubmissionTranscript = (conversationId: string) => {
  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [error, setError] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)

  useEffect(() => {
    let ignore = false
    const load = async () => {
      const nextDetail = await fetchInboxDetailPage(conversationId)
      if (ignore) {
        return
      }
      if (nextDetail === null) {
        setError(true)
        return
      }
      setDetail(nextDetail)
    }
    void load()
    return () => {
      ignore = true
    }
  }, [conversationId])

  const beforeId = detail?.older_before_id
  const detailId = detail?.id
  const loadOlder = useCallback(async () => {
    if (beforeId == null || detailId == null || loadingOlder) {
      return
    }
    setLoadingOlder(true)
    try {
      const older = await fetchInboxDetailPage(detailId, beforeId)
      if (older === null) {
        return
      }
      setDetail((current) =>
        current === null
          ? current
          : {
              ...current,
              messages: mergeInboxMessages(older.messages, current.messages),
              has_older: older.has_older,
              older_before_id: older.older_before_id,
            },
      )
    } finally {
      setLoadingOlder(false)
    }
  }, [beforeId, detailId, loadingOlder])

  return { detail, error, loadingOlder, loadOlder }
}

export const SubmissionDetailSheet = ({
  row,
  onClose,
}: {
  row: SubmissionRow
  onClose: (open: boolean) => void
}) => {
  const { detail, error, loadingOlder, loadOlder } = useSubmissionTranscript(row.id)
  const lines = useMemo(() => detail?.messages ?? [], [detail?.messages])

  return (
    <Sheet open onOpenChange={onClose}>
      <SheetContent
        side="right"
        className="bg-paper border-line w-full gap-0 p-0 data-[side=right]:sm:max-w-xl"
      >
        <SheetHeader className="border-line border-b px-5 py-4">
          <SheetTitle className="text-navy">{blank(row.visitor.name)}</SheetTitle>
          <SheetDescription className="text-mute text-xs">
            {`${STATE_LABEL[row.state] ?? row.state} · ${row.site_name}`}
          </SheetDescription>
        </SheetHeader>
        <TranscriptPane
          loading={detail === null && !error}
          error={error}
          lines={lines}
          hasOlder={detail?.has_older === true}
          loadingOlder={loadingOlder}
          onLoadOlder={loadOlder}
        />
      </SheetContent>
    </Sheet>
  )
}
