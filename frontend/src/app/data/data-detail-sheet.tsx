"use client"

import { useEffect, useMemo, useState } from "react"

import { Transcript } from "@/app/widget/transcript"
import type { ConversationDetail, InboxMessage } from "@/components/inbox/types"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { staffGet } from "@/lib/auth-client"

import { blank, STATE_LABEL, type SubmissionRow } from "./data-shared"

const TranscriptPane = ({
  loading,
  error,
  lines,
}: {
  loading: boolean
  error: boolean
  lines: InboxMessage[]
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
      <Transcript lines={lines} selfRole="agent" logLabel="Transcript" />
    </div>
  )
}

export const SubmissionDetailSheet = ({
  row,
  onClose,
}: {
  row: SubmissionRow
  onClose: (open: boolean) => void
}) => {
  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let ignore = false
    const load = async () => {
      const response = await staffGet(`/api/conversations/${row.id}`)
      if (ignore) {
        return
      }
      if (!response.ok) {
        setError(true)
        return
      }
      setDetail((await response.json()) as ConversationDetail)
    }
    void load()
    return () => {
      ignore = true
    }
  }, [row.id])

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
        <TranscriptPane loading={detail === null && !error} error={error} lines={lines} />
      </SheetContent>
    </Sheet>
  )
}
