/* oxlint-disable react-perf/jsx-no-new-function-as-prop */
/* oxlint-disable react-perf/jsx-no-jsx-as-prop */

"use client"

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
          <button
            type="button"
            className="border-line bg-ice text-navy focus-visible:outline-steel mt-2 inline-flex cursor-pointer rounded border px-2 py-0.5 text-xs font-semibold tracking-wide focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            aria-describedby={describedBy}
            aria-label={`${label}: ${title}`}
            onClick={handleOpen}
            onKeyDown={handleKeyDown}
          />
        }
      >
        {label}
      </HoverCardTrigger>
      <HoverCardContent className="border-line bg-paper text-ink w-64 p-3 shadow-sm">
        <p className="text-navy text-sm font-semibold">{title}</p>
        {href ? (
          <button
            type="button"
            className="text-steel focus-visible:outline-steel mt-2 inline-flex cursor-pointer text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={handleOpen}
          >
            Learn more
          </button>
        ) : null}
      </HoverCardContent>
    </HoverCard>
  )
}
