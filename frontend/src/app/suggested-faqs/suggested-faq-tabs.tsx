"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Each tab selects its own view. */

import type { KeyboardEvent } from "react"

import type { GapView } from "./suggested-faq-model"

export const VIEWS: { id: GapView; label: string }[] = [
  { id: "open", label: "Open" },
  { id: "answered", label: "Answered" },
  { id: "dismissed", label: "Dismissed" },
]

const tabId = (view: GapView) => `suggested-faq-tab-${view}`

// WAI-ARIA tabs: only the selected tab is in the tab order; arrows, Home and End move between them.
const targetIndex = (key: string, index: number) => {
  if (key === "ArrowRight") return (index + 1) % VIEWS.length
  if (key === "ArrowLeft") return (index - 1 + VIEWS.length) % VIEWS.length
  if (key === "Home") return 0
  if (key === "End") return VIEWS.length - 1
  return null
}

export const ViewTabs = ({
  view,
  onSelect,
}: {
  view: GapView
  onSelect: (view: GapView) => void
}) => {
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const next = targetIndex(event.key, index)
    if (next === null) return
    event.preventDefault()
    onSelect(VIEWS[next].id)
    document.getElementById(tabId(VIEWS[next].id))?.focus()
  }

  return (
    <div role="tablist" aria-label="Questions" className="border-line flex gap-1 border-b">
      {VIEWS.map((item, index) => (
        <button
          key={item.id}
          id={tabId(item.id)}
          type="button"
          role="tab"
          aria-selected={view === item.id}
          tabIndex={view === item.id ? 0 : -1}
          onClick={() => onSelect(item.id)}
          onKeyDown={(event) => handleKeyDown(event, index)}
          className={`focus-visible:ring-steel -mb-px border-b-2 px-4 py-2.5 text-sm font-semibold outline-none focus-visible:ring-2 ${
            view === item.id
              ? "border-ember text-navy"
              : "text-mute hover:text-navy border-transparent"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
