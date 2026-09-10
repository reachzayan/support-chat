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
