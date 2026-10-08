"use client"

import { useCallback, useEffect, useState } from "react"

import { staffRead, staffWrite, type HandoffContextRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import { HandoffCardDialog } from "./handoff-card-dialog"
import { handoffReasonLabel, handoffRouteLabel, REASON_STYLES } from "./handoff-utils"

type HandoffCardProps = {
  conversationId: string
  isAdmin: boolean
}

const HandoffLabel = ({ reason, resolved }: { reason: string; resolved: boolean }) => (
  <>
    <Badge
      className={`${REASON_STYLES[reason] ?? "bg-ice-2 text-ink"} pointer-events-none hidden tracking-normal normal-case sm:inline-flex`}
    >
      {handoffReasonLabel(reason)}
    </Badge>
    <span className="sm:hidden">Handoff</span>
    <span className="hidden sm:inline">
      {resolved ? "Handoff outcome saved" : "Handoff context"}
    </span>
  </>
)

const HandoffCardInner = ({ conversationId, isAdmin }: HandoffCardProps) => {
  const [handoff, setHandoff] = useState<HandoffContextRecord | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [open, setOpen] = useState(false)
  const [regenError, setRegenError] = useState(false)

  useEffect(() => {
    let ignore = false
    const load = async () => {
      const response = await staffRead(`/api/conversations/${conversationId}/handoff`)
      if (ignore) {
        return
      }
      if (response.status === 404) {
        setHandoff(null)
        setOpen(false)
        return
      }
      if (!response.ok) {
        setLoadError(true)
        setOpen(false)
        return
      }
      setLoadError(false)
      const next = (await response.json()) as HandoffContextRecord
      setHandoff(next)
    }
    void load()
    return () => {
      ignore = true
    }
  }, [conversationId])

  const handleOpenChange = useCallback((next: boolean) => setOpen(next), [])
  const handleOpen = useCallback(() => setOpen(true), [])
  const handleRegenerate = useCallback(async () => {
    if (handoff === null) {
      return
    }
    const response = await staffWrite(`/api/handoffs/${handoff.id}/summary/regenerate`, "POST", {})
    if (!response.ok) {
      setRegenError(true)
      return
    }
    setRegenError(false)
    setHandoff((await response.json()) as HandoffContextRecord)
  }, [handoff])
  const handleResolved = useCallback((outcome: NonNullable<HandoffContextRecord["outcome"]>) => {
    setHandoff((current) => (current === null ? current : { ...current, outcome }))
  }, [])

  if (loadError || handoff === null) return null

  const reasonClass = REASON_STYLES[handoff.escalation_reason] ?? "bg-ice-2 text-ink"
  const resolved = handoff.outcome !== null

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        onClick={handleOpen}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={resolved ? "Handoff outcome saved" : "Handoff context"}
        className="border-line bg-ice text-navy hover:bg-ice-2 focus-visible:ring-steel flex min-h-11 shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none xl:min-h-0"
      >
        <HandoffLabel reason={handoff.escalation_reason} resolved={resolved} />
      </Button>
      <HandoffCardDialog
        handoff={handoff}
        open={open}
        isAdmin={isAdmin}
        reasonClass={reasonClass}
        routeLabel={handoffRouteLabel(handoff)}
        resolved={resolved}
        onOpenChange={handleOpenChange}
        onRegenerate={handleRegenerate}
        regenError={regenError}
        onResolved={handleResolved}
      />
    </>
  )
}

export const HandoffCard = ({ conversationId, isAdmin }: HandoffCardProps) => (
  <HandoffCardInner key={conversationId} conversationId={conversationId} isAdmin={isAdmin} />
)
