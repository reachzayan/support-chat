"use client"

import { Transcript } from "@/app/widget/transcript"

import type { InboxMessage } from "./types"

type TranscriptPaneProps = {
  lines: InboxMessage[]
  muted?: boolean
}

export const TranscriptPane = ({ lines, muted = false }: TranscriptPaneProps) => {
  return <Transcript lines={lines} selfRole="agent" logLabel="Transcript" muted={muted} />
}
