"use client"

import { Flame } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { staffRead } from "@/components/admin/staff-api"

type BadgeGap = { conversations: number; spiking: boolean }

// Tells the agent that the visitor in front of them is one of several asking the same
// unanswered question. It links to the queue; approving answers is not an agent's job.
export const HotGapBadge = ({ conversationId }: { conversationId: string }) => {
  const [gap, setGap] = useState<BadgeGap | null>(null)

  useEffect(() => {
    let active = true
    const lookUp = async () => {
      try {
        const response = await staffRead(`/api/conversations/${conversationId}/knowledge-gap`)
        if (!response.ok) return
        const body = (await response.json()) as { gap?: BadgeGap | null } | null
        // A hint must never be able to take the inbox down, whatever the server sends back.
        if (active) setGap(body?.gap ?? null)
      } catch {
        // The badge is a hint; the inbox works without it.
      }
    }
    void lookUp()
    return () => {
      active = false
    }
  }, [conversationId])

  if (gap === null) return null
  return (
    <Link
      href="/admin/suggested-faqs"
      className="bg-ember/10 text-ember focus-visible:ring-steel inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold outline-none focus-visible:ring-2"
    >
      <Flame aria-hidden="true" className="size-3" strokeWidth={2.4} />
      {gap.spiking ? "Spiking question" : "Repeated question"}
      <span className="font-semibold">
        · Asked in {gap.conversations} {gap.conversations === 1 ? "chat" : "chats"}
      </span>
    </Link>
  )
}
