"use client"

type ChatStatusProps = {
  reconnecting: boolean
  systemReason?: string | null
}

const STATUS_BY_REASON: Record<string, string> = {
  visitor_request: "A specialist will join this chat shortly.",
  sensitive: "A specialist can help through a secure channel.",
  individual_case: "A specialist is required for this case.",
  retrieval_miss: "Looking for a specialist to pick this up.",
  sufficiency_fail: "A specialist can help finish this safely.",
  provider_timeout: "Temporary issue — a specialist can take it from here.",
  tech_fail: "Temporary issue — a specialist can take it from here.",
  repeated_miss: "Handing you to a specialist so you don't have to repeat yourself.",
  policy_boundary: "A specialist can walk you through this in the right channel.",
  rate_ceiling: "Temporary limit — a specialist can take over.",
  off_topic: "Outside chat scope — a specialist can take a look.",
  out_of_scope: "Outside chat scope — a specialist can take a look.",
  escalate: "A specialist will join this chat shortly.",
  insufficient: "Looking for a specialist to pick this up.",
}

export const statusLiteralForReason = (reason: string | null | undefined) => {
  if (!reason) {
    return null
  }
  return STATUS_BY_REASON[reason] ?? null
}

export const ChatStatus = ({ reconnecting, systemReason = null }: ChatStatusProps) => {
  if (reconnecting) {
    return (
      <output
        aria-live="polite"
        className="widget-enter text-mute mx-3 mt-1 flex items-center gap-2 rounded-2xl bg-white/66 px-3 py-2.5 text-xs font-semibold shadow-[0_6px_18px_rgba(13,31,58,0.06)] backdrop-blur-xl"
      >
        <span className="bg-ember size-1.5 rounded-full" />
        Reconnecting…
      </output>
    )
  }
  const status = statusLiteralForReason(systemReason)
  if (!status) {
    return null
  }
  return (
    <output
      aria-live="polite"
      className="widget-enter text-mute mx-3 mt-1 flex items-center gap-2 rounded-2xl bg-white/66 px-3 py-2.5 text-xs font-semibold shadow-[0_6px_18px_rgba(13,31,58,0.06)] backdrop-blur-xl"
    >
      <span className="bg-steel size-1.5 rounded-full" />
      {status}
    </output>
  )
}
