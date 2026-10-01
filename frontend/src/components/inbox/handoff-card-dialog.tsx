"use client"

import { useCallback } from "react"

import { RetryError } from "@/components/admin/retry-error"
import type { HandoffContextRecord } from "@/components/admin/staff-api"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { CandidateEvidenceList } from "./candidate-evidence-list"
import { HandoffDialogMeta, HandoffMachineSummary } from "./handoff-dialog-sections"
import { HandoffOutcomeForm } from "./handoff-outcome-form"

const TIMING_KEYS = [
  "intent_ms",
  "fast_path_ms",
  "retrieval_ms",
  "model_ms",
  "sufficiency_ms",
] as const

const EMPTY_CANDIDATES: HandoffContextRecord["candidates"] = []

type HandoffCardDialogProps = {
  handoff: HandoffContextRecord
  open: boolean
  isAdmin: boolean
  reasonClass: string
  routeLabel: string
  resolved: boolean
  onOpenChange: (open: boolean) => void
  onRegenerate: () => void
  regenError: boolean
  onResolved: (outcome: NonNullable<HandoffContextRecord["outcome"]>) => void
}

const HandoffResolvedBlock = ({
  outcome,
}: {
  outcome: NonNullable<HandoffContextRecord["outcome"]>
}) => (
  <div className="bg-ice rounded-[8px] px-3 py-2">
    <p className="text-navy heading text-sm">Resolved: {outcome.outcome.replaceAll("_", " ")}</p>
    {outcome.note ? <p className="text-mute mt-1 text-xs leading-5">{outcome.note}</p> : null}
  </div>
)

const StageTimings = ({ handoff }: { handoff: HandoffContextRecord }) => {
  const timings = handoff.provider_stage_timings || {}
  const timingEntries = TIMING_KEYS.filter(
    (key) => timings[key] !== undefined && timings[key] !== null,
  )
  if (timingEntries.length === 0) {
    return <p className="text-mute text-xs">No stage timings recorded.</p>
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
      {timingEntries.map((key) => (
        <div key={key} className="flex justify-between gap-2 text-xs">
          <dt className="text-mute font-mono">{key}</dt>
          <dd className="text-ink font-mono">{timings[key]} ms</dd>
        </div>
      ))}
    </dl>
  )
}

export const HandoffCardDialog = ({
  handoff,
  open,
  isAdmin,
  reasonClass,
  routeLabel,
  resolved,
  onOpenChange,
  onRegenerate,
  regenError,
  onResolved,
}: HandoffCardDialogProps) => {
  const handleResolved = useCallback(
    (outcome: { outcome: string; note: string | null; resolved_at: string }) => {
      onResolved({
        outcome: outcome.outcome,
        note: outcome.note,
        resolved_at: outcome.resolved_at,
      })
    },
    [onResolved],
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 p-0" data-slot="handoff-panel">
        <DialogHeader>
          <DialogTitle>Handoff context</DialogTitle>
          <DialogDescription>
            Context for this conversation only. Close to return to the transcript.
          </DialogDescription>
          <HandoffDialogMeta handoff={handoff} reasonClass={reasonClass} routeLabel={routeLabel} />
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-none px-5 py-4">
          <blockquote className="border-line bg-ice text-ink border-l-steel rounded-[8px] border-l-4 px-3 py-2 font-mono text-xs leading-5">
            {handoff.original_question}
          </blockquote>

          <HandoffMachineSummary
            handoff={handoff}
            isAdmin={isAdmin}
            resolved={resolved}
            onRegenerate={onRegenerate}
          />
          {regenError ? (
            <RetryError
              text="Could not regenerate the summary."
              onRetry={onRegenerate}
              className="mt-0"
            />
          ) : null}

          <Collapsible defaultOpen={false}>
            <CollapsibleTrigger aria-label="Technical details">
              <span>Technical details</span>
              <span className="text-mute text-xs font-normal">Show</span>
            </CollapsibleTrigger>
            <CollapsibleContent className="flex flex-col gap-3">
              <CandidateEvidenceList candidates={handoff.candidates ?? EMPTY_CANDIDATES} />
              <StageTimings handoff={handoff} />
            </CollapsibleContent>
          </Collapsible>
        </div>
        <div className="border-line bg-paper shrink-0 border-t px-5 py-4">
          {resolved && handoff.outcome ? (
            <HandoffResolvedBlock outcome={handoff.outcome} />
          ) : (
            <HandoffOutcomeForm handoffId={handoff.id} onResolved={handleResolved} />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
