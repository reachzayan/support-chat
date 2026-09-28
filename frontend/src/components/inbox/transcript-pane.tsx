"use client"

import { Transcript } from "@/app/widget/transcript"

import type { InboxMessage } from "./types"

type TranscriptPaneProps = {
  lines: InboxMessage[]
  muted?: boolean
  companyName?: string | null
  agentName?: string | null
}

export const TranscriptPane = ({
  lines,
  muted = false,
  companyName = null,
  agentName = null,
}: TranscriptPaneProps) => {
  return (
    <Transcript
      lines={lines}
      selfRole="agent"
      logLabel="Transcript"
      muted={muted}
      companyName={companyName}
      agentName={agentName}
    />
  )
}
