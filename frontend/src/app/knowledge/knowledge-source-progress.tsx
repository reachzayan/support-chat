import type { KbSourceRecord } from "@/components/admin/staff-api"

import { humanizeCode } from "./knowledge-format"

const ingestIsActive = (source: KbSourceRecord) =>
  source.status !== "ready" &&
  (source.status === "running" ||
    source.stage === "discovering" ||
    source.stage === "processing" ||
    source.stage === "validating" ||
    source.stage === "promoting")

export const sourceIsSyncing = (source: KbSourceRecord) =>
  ingestIsActive(source) || source.status === "running" || source.status === "queued"

export const sourceSyncActionLabel = (source: KbSourceRecord) => {
  if (source.source_kind === "text") return "Reprocess"
  if (source.status === "failed" || (source.pages_failed ?? 0) > 0) return "Retry crawl"
  return "Sync"
}
export const sourceStatusLabel = (source: KbSourceRecord) => {
  if (ingestIsActive(source) || source.status === "running") {
    return "Syncing"
  }
  if (source.status === "queued") {
    return "Queued"
  }
  if (source.status === "failed") {
    const reason = sourceFailureReason(source)
    if (source.snapshot_state === "live") {
      return reason ? `Sync failed — live unchanged (${reason})` : "Sync failed — live unchanged"
    }
    return reason ? `Failed — ${reason}` : "Failed"
  }
  return "Ready"
}

const sourceFailureReason = (source: KbSourceRecord) => {
  const rules = source.validation_errors ?? []
  if (rules.length > 0) {
    return rules.map(humanizeCode).join(", ")
  }
  const code = source.error_code ?? source.snapshot_error_code
  return code ? humanizeCode(code) : null
}

const STAGE_LABELS: Record<string, string> = {
  discovering: "Discovering pages",
  validating: "Validating snapshot",
  promoting: "Promoting snapshot",
}

const ingestProgressLabel = (source: KbSourceRecord, discovered: number, embedded: number) => {
  const stageLabel = STAGE_LABELS[source.stage ?? ""]
  if (stageLabel) return stageLabel
  if (discovered > 0) {
    return `Processing ${embedded} of ${discovered} pages`
  }
  return source.status
}

const sourceNextStep = (source: KbSourceRecord) => {
  const rules = source.validation_errors ?? []
  if (rules.length > 0) {
    return "Live answers were left unchanged. Review the failed rule, then retry the crawl."
  }
  if ((source.pages_failed ?? 0) > 0) {
    return "Open a failed page and retry it, or retry the crawl."
  }
  if (source.status === "failed") {
    return "Review crawl activity, then retry the crawl."
  }
  return null
}

const IngestProgressBar = ({
  source,
  discovered,
  embedded,
}: {
  source: KbSourceRecord
  discovered: number
  embedded: number
}) => {
  return (
    <>
      {discovered > 0 ? (
        <progress
          aria-label="Ingestion progress"
          aria-valuemin={0}
          aria-valuemax={discovered}
          aria-valuenow={embedded}
          max={discovered}
          value={embedded}
          className="bg-ice-2 [&::-moz-progress-bar]:bg-steel [&::-webkit-progress-bar]:bg-ice-2 [&::-webkit-progress-value]:bg-steel h-1.5 w-full overflow-hidden rounded-full [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:transition-[width] [&::-webkit-progress-value]:duration-200"
        />
      ) : null}
      <span>{ingestProgressLabel(source, discovered, embedded)}</span>
    </>
  )
}

const SourceFailureHints = ({ failed, nextStep }: { failed: number; nextStep: string | null }) => (
  <>
    {failed > 0 ? (
      <span className="text-ember text-[10px] font-bold">
        {failed} {failed === 1 ? "page" : "pages"} failed
      </span>
    ) : null}
    {nextStep !== null ? <span className="text-mute">{nextStep}</span> : null}
  </>
)

export const SourceProgress = ({ source }: { source: KbSourceRecord }) => {
  const discovered = source.pages_discovered ?? 0
  const embedded = source.pages_embedded ?? 0
  const failed = source.pages_failed ?? 0
  const active = ingestIsActive(source)
  const nextStep = active ? null : sourceNextStep(source)
  if (!active && failed === 0 && nextStep === null) {
    return null
  }
  return (
    <div className="flex flex-col gap-1">
      {active ? (
        <IngestProgressBar source={source} discovered={discovered} embedded={embedded} />
      ) : null}
      <SourceFailureHints failed={failed} nextStep={nextStep} />
    </div>
  )
}
