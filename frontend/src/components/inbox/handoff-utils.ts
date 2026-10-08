import type { HandoffContextRecord } from "@/components/admin/staff-api"

export const REASON_STYLES: Record<string, string> = {
  retrieval_miss: "bg-ember-soft/30 text-ember",
  sufficiency_fail: "bg-ember-soft/30 text-ember",
  sensitive: "bg-steel/15 text-steel",
  policy_boundary: "bg-steel/15 text-steel",
  provider_timeout: "bg-mute/20 text-mute",
  rate_ceiling: "bg-mute/20 text-mute",
  repeated_miss: "bg-navy/10 text-navy",
  visitor_request: "bg-navy/10 text-navy",
  off_topic: "bg-ice-2 text-ink",
  individual_case: "bg-steel/15 text-steel",
}

const REASON_LABELS: Record<string, string> = {
  visitor_request: "Visitor asked for a specialist",
  sensitive: "Sensitive topic",
  individual_case: "Individual case",
  retrieval_miss: "No matching answer found",
  sufficiency_fail: "Answer not sufficient",
  provider_timeout: "Assistant timed out",
  repeated_miss: "Repeated unanswered questions",
  policy_boundary: "Outside policy boundary",
  rate_ceiling: "Usage limit reached",
  off_topic: "Off topic",
}

export const handoffReasonLabel = (reason: string) => {
  const known = REASON_LABELS[reason]
  if (known) return known
  const words = reason.trim().replace(/[_-]+/g, " ").toLowerCase()
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Unknown reason"
}

export const formatHandoffWhen = (value: string | null) => {
  if (!value) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export const handoffRouteLabel = (handoff: HandoffContextRecord) =>
  handoff.route === "live_queue"
    ? "Live queue"
    : `Callback by ${formatHandoffWhen(handoff.promised_response_by) ?? "configured window"}`
