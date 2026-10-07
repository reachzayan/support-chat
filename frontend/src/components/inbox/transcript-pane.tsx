"use client"

import { Transcript, isClosedNotice } from "@/app/widget/transcript"

import type { InboxMessage } from "./types"

type TranscriptPaneProps = {
  lines: InboxMessage[]
  muted?: boolean
  closed?: boolean
  companyName?: string | null
  agentName?: string | null
}

export const TranscriptPane = ({
  lines,
  muted = false,
  closed = false,
  companyName = null,
  agentName = null,
}: TranscriptPaneProps) => {
  const notice = closed && !lines.some(isClosedNotice) ? "This chat is closed" : undefined
  return (
    <Transcript
      autoFollow
      lines={lines}
      selfRole="agent"
      logLabel="Transcript"
      muted={muted}
      notice={notice}
      conversationState={closed ? "closed" : null}
      companyName={companyName}
      agentName={agentName}
    />
  )
}
