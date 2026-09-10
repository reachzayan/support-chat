"use client"

import type { HandoffContextRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

import { formatHandoffWhen } from "./handoff-utils"

export const HandoffDialogMeta = ({
  handoff,
  reasonClass,
  routeLabel,
}: {
  handoff: HandoffContextRecord
  reasonClass: string
  routeLabel: string
}) => (
  <div className="mt-2 flex flex-wrap items-center gap-2">
    <Badge className={reasonClass} aria-label={`Escalation reason: ${handoff.escalation_reason}`}>
      {handoff.escalation_reason}
    </Badge>
    <Badge className="bg-ice-2 text-navy tracking-normal normal-case">{routeLabel}</Badge>
    <span className="text-mute text-xs">{formatHandoffWhen(handoff.created_at)}</span>
  </div>
)

export const HandoffMachineSummary = ({
  handoff,
  isAdmin,
  resolved,
  onRegenerate,
}: {
  handoff: HandoffContextRecord
  isAdmin: boolean
  resolved: boolean
  onRegenerate: () => void
}) => (
  <section role="note" aria-labelledby={`machine-summary-${handoff.id}`}>
    <div className="mb-1 flex items-center justify-between gap-2">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger
            id={`machine-summary-${handoff.id}`}
            className="text-mute text-[10px] font-bold tracking-[0.12em] uppercase"
          >
            Machine summary
          </TooltipTrigger>
          <TooltipContent>Generated automatically. Verify before acting.</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {isAdmin && !resolved ? (
        <Button
          type="button"
          variant="ghost"
          size="xs"
          onClick={onRegenerate}
          className="text-steel h-7 px-2 text-xs font-bold"
        >
          Regenerate
        </Button>
      ) : null}
    </div>
    <p className="text-ink text-sm leading-6">{handoff.machine_summary || "Summary pending."}</p>
  </section>
)
