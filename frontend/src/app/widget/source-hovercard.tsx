/* oxlint-disable react-perf/jsx-no-new-function-as-prop */
/* oxlint-disable react-perf/jsx-no-jsx-as-prop */

"use client"

import { Button } from "@/components/ui/button"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"

import { openUrlOnHost } from "./host-bridge"

export type SourceCitation = {
  source_urls?: string[] | null
  display_locator?: string | null
  source_title?: string | null
  cited_text?: string | null
}

const learnMoreHref = (citation: SourceCitation) =>
  citation.source_urls?.find((item) => item.trim().length > 0) ?? null

const hostFromHref = (href: string | null) => {
  if (!href) {
    return null
  }
  try {
    return new URL(href).hostname.replace(/^www\./, "")
  } catch {
    return null
  }
}

type SourceHoverCardProps = {
  citation: SourceCitation
  describedBy: string
  label?: string
}

export const SourceHoverCard = ({
  citation,
  describedBy,
  label = "Source",
}: SourceHoverCardProps) => {
  const href = learnMoreHref(citation)
  if (!href && !citation.source_title) {
    return null
  }
  const title = citation.source_title?.trim() || "Knowledge base"
  const host = hostFromHref(href)
  const handleOpen = (event: { preventDefault: () => void }) => {
    event.preventDefault()
    if (!href) {
      return
    }
    openUrlOnHost(href)
  }
  const handleKeyDown = (event: { key: string; preventDefault: () => void }) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      handleOpen(event)
    }
  }
  return (
    <HoverCard>
      <HoverCardTrigger
        render={
          <Button
            type="button"
            variant="outline"
            className="border-line bg-paper text-ink hover:bg-ice-2 focus-visible:outline-steel h-auto min-h-0 w-full min-w-0 flex-col items-start justify-start gap-0.5 rounded-xl px-3 py-2.5 text-left leading-5 font-normal whitespace-normal"
            aria-describedby={describedBy}
            aria-label={`${label}: ${title}`}
            onClick={handleOpen}
            onKeyDown={handleKeyDown}
          />
        }
      >
        <span className="line-clamp-2 w-full text-sm font-medium">{title}</span>
        {host ? (
          <span className="text-mute w-full truncate text-xs font-normal">{host}</span>
        ) : null}
      </HoverCardTrigger>
      <HoverCardContent className="border-line bg-paper text-ink w-64 p-3 shadow-sm">
        <p className="text-navy text-sm font-semibold">{title}</p>
        {href ? (
          <Button
            type="button"
            variant="link"
            className="text-steel focus-visible:outline-steel mt-2 inline-flex cursor-pointer text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={handleOpen}
          >
            Learn more
          </Button>
        ) : null}
      </HoverCardContent>
    </HoverCard>
  )
}
