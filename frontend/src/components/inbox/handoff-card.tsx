"use client"

import { useCallback, useEffect, useState } from "react"

import { staffRead, staffWrite, type HandoffContextRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"

import { HandoffCardDialog } from "./handoff-card-dialog"
import { handoffRouteLabel, REASON_STYLES } from "./handoff-utils"

type HandoffCardProps = {
  conversationId: string
  isAdmin: boolean
}

const HandoffCardInner = ({ conversationId, isAdmin }: HandoffCardProps) => {
  const [handoff, setHandoff] = useState<HandoffContextRecord | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [open, setOpen] = useState(false)

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
      setOpen(next.outcome === null)
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
      return
    }
    setHandoff((await response.json()) as HandoffContextRecord)
  }, [handoff])
  const handleResolved = useCallback((outcome: NonNullable<HandoffContextRecord["outcome"]>) => {
    setHandoff((current) => (current === null ? current : { ...current, outcome }))
  }, [])

  if (loadError || handoff === null) {
    return null
  }

  const reasonClass = REASON_STYLES[handoff.escalation_reason] ?? "bg-ice-2 text-ink"
  const resolved = handoff.outcome !== null

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="border-line bg-ice text-navy hover:bg-ice-2 focus-visible:ring-steel flex shrink-0 items-center gap-2 rounded-[8px] border px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
      >
        <Badge className={`${reasonClass} pointer-events-none`}>{handoff.escalation_reason}</Badge>
        <span>{resolved ? "Handoff resolved" : "Handoff context"}</span>
      </button>
      <HandoffCardDialog
        handoff={handoff}
        open={open}
        isAdmin={isAdmin}
        reasonClass={reasonClass}
        routeLabel={handoffRouteLabel(handoff)}
        resolved={resolved}
        onOpenChange={handleOpenChange}
        onRegenerate={handleRegenerate}
        onResolved={handleResolved}
      />
    </>
  )
}

export const HandoffCard = ({ conversationId, isAdmin }: HandoffCardProps) => (
  <HandoffCardInner key={conversationId} conversationId={conversationId} isAdmin={isAdmin} />
)
