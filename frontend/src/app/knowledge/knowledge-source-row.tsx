import { cn } from "cn"
import { ChevronDown, FileText, Globe2, RefreshCw } from "lucide-react"
import { motion } from "motion/react"
import { useCallback } from "react"

import type { KbPageRecord, KbSourceRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { LinkButton, linkUnderlineClass } from "@/components/ui/link-button"
import { Spinner } from "@/components/ui/spinner"

import {
  sourceIsSyncing,
  SourceProgress,
  sourceStatusLabel,
  sourceSyncActionLabel,
} from "./knowledge-source-progress"
import type { SourceRowProps } from "./knowledge-source-types"

const RAIL_SPRING = { type: "spring", stiffness: 500, damping: 42, mass: 0.6 } as const
const SourceRowActions = ({
  source,
  isAdmin,
  onSync,
  onToggle,
  onDelete,
  onViewChanges,
}: {
  source: KbSourceRecord
  isAdmin: boolean
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => {
  const handleSync = useCallback(() => onSync(source), [onSync, source])
  const handleToggle = useCallback(() => onToggle(source), [onToggle, source])
  const handleDelete = useCallback(() => onDelete(source), [onDelete, source])
  const handleViewChanges = useCallback(() => onViewChanges(source), [onViewChanges, source])
  const syncing = sourceIsSyncing(source)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <LinkButton type="button" onClick={handleViewChanges}>
        View progress
      </LinkButton>
      {isAdmin ? (
        <>
          <LinkButton type="button" onClick={handleSync} disabled={syncing}>
            {syncing ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <RefreshCw aria-hidden="true" data-icon="inline-start" className="size-3.5" />
            )}
            {sourceSyncActionLabel(source)}
          </LinkButton>
          <LinkButton
            type="button"
            variant={source.enabled ? "emphasis" : "default"}
            onClick={handleToggle}
          >
            {source.enabled ? "Disable" : "Enable"}
          </LinkButton>
          <LinkButton type="button" variant="ember" onClick={handleDelete}>
            Delete
          </LinkButton>
        </>
      ) : null}
    </div>
  )
}

const SelectedRail = ({ layoutId }: { layoutId: string }) => (
  <motion.span
    layoutId={layoutId}
    transition={RAIL_SPRING}
    aria-hidden="true"
    className="bg-steel absolute top-2 bottom-2 left-0 w-0.5 rounded-full"
  />
)

const SourcePages = ({
  pages,
  selectedPageId,
  onSelectPage,
}: {
  pages: KbPageRecord[]
  selectedPageId: string | null
  onSelectPage: (page: KbPageRecord) => void
}) => {
  if (pages.length === 0) {
    return <p className="text-mute px-1 py-2 text-xs">No pages yet.</p>
  }
  return (
    <ul className="flex flex-col gap-0.5 pb-1">
      {pages.map((page) => (
        <SourcePageRow
          key={page.id}
          page={page}
          selected={page.id === selectedPageId}
          onSelect={onSelectPage}
        />
      ))}
    </ul>
  )
}

const SourcePageRow = ({
  page,
  selected,
  onSelect,
}: {
  page: KbPageRecord
  selected: boolean
  onSelect: (page: KbPageRecord) => void
}) => {
  const handleSelect = useCallback(() => onSelect(page), [onSelect, page])
  return (
    <li>
      <Button
        type="button"
        variant="ghost"
        onClick={handleSelect}
        aria-current={selected ? "true" : undefined}
        aria-label={page.title}
        className="focus-visible:ring-steel h-auto w-full justify-start rounded-lg px-2 py-1.5 text-left focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="block max-w-full min-w-0 truncate text-left">
          <span
            className={cn(
              linkUnderlineClass,
              "inline text-sm",
              selected
                ? "text-navy after:scale-x-100 font-semibold"
                : "text-steel after:scale-x-100 after:opacity-40 hover:text-navy hover:after:opacity-100",
            )}
          >
            {page.title}
          </span>
        </span>
      </Button>
    </li>
  )
}

const SourceRowTrigger = ({
  source,
  onSelect,
}: {
  source: KbSourceRecord
  onSelect: () => void
}) => (
  <CollapsibleTrigger onClick={onSelect} className="group h-auto w-full gap-2 rounded-lg py-1">
    <span className="flex min-w-0 flex-1 items-center gap-2">
      <span className="text-navy min-w-0 truncate text-sm font-semibold">
        {source.display_name || source.start_url}
      </span>
      {source.source_kind === "text" ? <Badge>Text</Badge> : null}
    </span>
    <span className="text-mute flex shrink-0 items-center gap-1.5 font-mono text-[10px] tabular-nums">
      {source.page_count} {source.page_count === 1 ? "page" : "pages"}
      <ChevronDown
        aria-hidden="true"
        className="size-4 transition-transform duration-200 ease-out group-aria-expanded:rotate-180"
      />
    </span>
  </CollapsibleTrigger>
)

const SourceRowBody = ({
  source,
  pages,
  selectedPageId,
  isAdmin,
  onSync,
  onToggle,
  onDelete,
  onSelectPage,
  onViewChanges,
  onSelect,
}: Omit<SourceRowProps, "selected" | "onSelect"> & { onSelect: () => void }) => {
  const Icon = source.source_kind === "text" ? FileText : Globe2
  return (
    <div className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className="bg-ice text-steel mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-[8px]"
      >
        <Icon className="size-4" strokeWidth={1.8} />
      </span>
      <div className="min-w-0 flex-1">
        <SourceRowTrigger source={source} onSelect={onSelect} />
        <div className="text-mute mt-2 flex flex-col gap-1 text-xs" aria-live="polite">
          <span className="text-ink inline-flex items-center gap-1.5 font-semibold">
            <span
              className={`size-2 rounded-full ${source.status === "ready" ? "bg-[#29915E]" : "bg-ember"}`}
            />
            {sourceStatusLabel(source)}
          </span>
          <SourceProgress source={source} />
        </div>
        <div className="mt-3">
          <SourceRowActions
            source={source}
            isAdmin={isAdmin}
            onSync={onSync}
            onToggle={onToggle}
            onDelete={onDelete}
            onViewChanges={onViewChanges}
          />
        </div>
        <CollapsibleContent className="mt-3">
          <SourcePages pages={pages} selectedPageId={selectedPageId} onSelectPage={onSelectPage} />
        </CollapsibleContent>
      </div>
    </div>
  )
}

export const SourceRow = ({
  source,
  pages,
  selected,
  selectedPageId,
  isAdmin,
  onSelect,
  onSync,
  onToggle,
  onDelete,
  onSelectPage,
  onViewChanges,
}: SourceRowProps) => {
  const handleSelect = useCallback(() => onSelect(source), [onSelect, source])
  return (
    <li className="px-1 py-0.5">
      <div
        className={cn(
          "relative rounded-xl px-3 py-3 transition-colors duration-150",
          selected ? "bg-ice-2" : "hover:bg-ice-2/70",
        )}
      >
        {selected ? <SelectedRail layoutId="knowledge-source-rail" /> : null}
        <Collapsible open={selected}>
          <SourceRowBody
            source={source}
            pages={pages}
            selectedPageId={selectedPageId}
            isAdmin={isAdmin}
            onSync={onSync}
            onToggle={onToggle}
            onDelete={onDelete}
            onSelectPage={onSelectPage}
            onViewChanges={onViewChanges}
            onSelect={handleSelect}
          />
        </Collapsible>
      </div>
    </li>
  )
}
