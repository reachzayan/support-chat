"use client"

import { ChevronDown, ExternalLink, Globe2, Plus, RefreshCw } from "lucide-react"
import { useCallback, useMemo, useState, type ChangeEvent } from "react"

import type {
  KbPageDetail,
  KbPageRecord,
  KbSourceRecord,
  SiteRecord,
} from "@/components/admin/staff-api"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { safeHttpUrl } from "@/lib/ua"

import { useKnowledgeState } from "./knowledge-state"
import { SnapshotDiffSheet } from "./snapshot-diff-sheet"

type KnowledgeConsoleProps = {
  isAdmin: boolean
  displayName: string
}

export const KnowledgeConsole = ({ isAdmin, displayName: _displayName }: KnowledgeConsoleProps) => {
  const state = useKnowledgeState(isAdmin)
  const { handleAdd } = state
  const [addWebsiteOpen, setAddWebsiteOpen] = useState(false)
  const selectedSite = state.sites.find((site) => site.id === state.siteId) ?? null
  const handleAddWebsite = useCallback(async () => {
    const added = await handleAdd()
    if (added) {
      setAddWebsiteOpen(false)
    }
  }, [handleAdd])
  const handleOpenAddWebsite = useCallback(() => setAddWebsiteOpen(true), [])
  return (
    <div className="view-transition-enter bg-ice flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0">
        <StaffHeader
          title="Knowledge base"
          description="Add the public pages this site should answer from."
        />
      </div>
      <KnowledgeWebsiteBar
        isAdmin={isAdmin}
        selectedSite={selectedSite}
        sites={state.sites}
        siteId={state.siteId}
        sourceCount={state.sources.length}
        pageCount={state.pages.length}
        onSite={state.handleSite}
        onOpenAddWebsite={handleOpenAddWebsite}
      />
      <div id="main-content" className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-6 lg:px-8 lg:py-8">
          <SourceTable
            isAdmin={isAdmin}
            sources={state.sources}
            onSync={state.handleSync}
            onToggle={state.handleToggleSource}
            onDelete={state.handleDelete}
            onSelect={state.handleSelectSource}
            onViewChanges={state.handleViewChanges}
          />
          <SnapshotDiffSheet
            open={state.diffSource !== null}
            onOpenChange={state.handleDiffOpen}
            diff={state.diff}
            status={state.diffStatus}
            canRollback={isAdmin && state.canRollback}
            rollbackBusy={state.rollbackBusy}
            onRollback={state.handleRollback}
          />
          <PageTable
            pages={state.pages}
            selectedId={state.pageDetail?.id ?? null}
            isAdmin={isAdmin}
            onSelect={state.handleSelectPage}
            onToggle={state.handleTogglePage}
          />
          <IndexedCopy detail={state.pageDetail} />
        </div>
      </div>
      {isAdmin ? (
        <AddWebsiteDialog
          open={addWebsiteOpen}
          onOpenChange={setAddWebsiteOpen}
          siteName={selectedSite?.name ?? "this website"}
          urls={state.urls}
          onUrls={state.handleUrls}
          onAdd={handleAddWebsite}
          error={state.addError}
        />
      ) : null}
    </div>
  )
}

type KnowledgeWebsiteBarProps = {
  isAdmin: boolean
  selectedSite: SiteRecord | null
  sites: SiteRecord[]
  siteId: string
  sourceCount: number
  pageCount: number
  onSite: (siteId: string) => void
  onOpenAddWebsite: () => void
}

const KnowledgeWebsiteBar = ({
  isAdmin,
  selectedSite,
  sites,
  siteId,
  sourceCount,
  pageCount,
  onSite,
  onOpenAddWebsite,
}: KnowledgeWebsiteBarProps) => (
  <div className="border-line bg-paper shrink-0 border-b">
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-5 py-4 sm:flex-row sm:items-end sm:justify-between lg:px-8">
      <div className="flex min-w-0 flex-wrap items-center gap-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="bg-ice-2 text-steel flex size-10 shrink-0 items-center justify-center rounded-[10px]">
            <Globe2 aria-hidden="true" className="size-5" strokeWidth={1.8} />
          </span>
          <div className="min-w-0">
            <p className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase">
              Active website
            </p>
            <p className="text-navy truncate text-sm font-extrabold">
              {selectedSite?.name ?? "Choose a website"}
            </p>
          </div>
        </div>
        <div className="border-line hidden h-10 border-l sm:block" aria-hidden="true" />
        <div className="flex items-center gap-5">
          <OverviewMetric label="Sources" value={sourceCount} />
          <OverviewMetric label="Indexed pages" value={pageCount} />
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <SitePicker sites={sites} siteId={siteId} onSite={onSite} />
        {isAdmin ? (
          <Button
            type="button"
            onClick={onOpenAddWebsite}
            disabled={!siteId}
            className="bg-ember hover:bg-ember-mid focus-visible:ring-steel h-10 rounded-[9px] px-4 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
          >
            <Plus aria-hidden="true" />
            Add website
          </Button>
        ) : null}
      </div>
    </div>
  </div>
)

const OverviewMetric = ({ label, value }: { label: string; value: number }) => (
  <div className="border-line border-l pl-4 first:border-l-0 first:pl-0">
    <p className="text-mute text-[10px] font-bold tracking-[0.12em] uppercase">{label}</p>
    <p className="text-navy mt-1 text-xl font-extrabold tabular-nums">{value}</p>
  </div>
)

const SitePicker = ({
  compact = false,
  sites,
  siteId,
  onSite,
}: {
  compact?: boolean
  sites: SiteRecord[]
  siteId: string
  onSite: (siteId: string) => void
}) => {
  const items = useMemo(() => sites.map((site) => ({ label: site.name, value: site.id })), [sites])
  const handleSiteChange = useCallback(
    (value: string | null) => {
      if (typeof value === "string" && value.length > 0) {
        onSite(value)
      }
    },
    [onSite],
  )
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${compact ? "w-44" : "sm:w-56"}`}>
      <label
        className={`${compact ? "sr-only" : "text-mute text-[10px] font-bold tracking-[0.12em] uppercase"}`}
        htmlFor="knowledge-site"
      >
        Website
      </label>
      <Select
        value={siteId || null}
        onValueChange={handleSiteChange}
        items={items}
        id="knowledge-site"
      >
        <SelectTrigger
          aria-label="Site"
          className={`border-line bg-ice text-ink w-full min-w-0 cursor-pointer rounded-[9px] border px-3 text-sm ${compact ? "h-9 data-[size=default]:h-9" : "h-10 data-[size=default]:h-10"}`}
        >
          <SelectValue placeholder="Select a site" />
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false} align="start">
          <SelectGroup>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}

const AddWebsiteDialog = ({
  open,
  onOpenChange,
  siteName,
  urls,
  onUrls,
  onAdd,
  error,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteName: string
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onAdd: () => void
  error: string | null
}) => {
  const handleCancel = useCallback(() => onOpenChange(false), [onOpenChange])
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl gap-0 p-0">
        <DialogHeader className="bg-ice/70 px-6 py-5">
          <div className="bg-ember/10 text-ember mb-2 flex size-10 items-center justify-center rounded-[10px]">
            <Plus aria-hidden="true" className="size-5" strokeWidth={2.2} />
          </div>
          <DialogTitle className="text-lg tracking-[-0.025em]">Add website pages</DialogTitle>
          <DialogDescription className="max-w-md leading-5">
            Add public pages to {siteName}. We’ll index the content so the assistant can retrieve
            it.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 px-6 py-6">
          <div>
            <label className="text-ink block text-sm font-bold" htmlFor="knowledge-urls">
              Website URL
            </label>
            <p className="text-mute mt-1 text-xs">
              Use HTTPS. Add one page per line if you have more than one.
            </p>
          </div>
          <Textarea
            id="knowledge-urls"
            name="pageUrls"
            autoComplete="off"
            aria-label="Website URL"
            value={urls}
            onChange={onUrls}
            placeholder="https://example.com/services"
            className="border-line bg-ice text-ink focus-visible:ring-steel min-h-24 w-full resize-y rounded-[9px] border px-3 py-3 font-mono text-sm leading-6 outline-none focus-visible:ring-2"
            rows={3}
            aria-invalid={error ? "true" : undefined}
            aria-describedby={error ? "knowledge-urls-error" : undefined}
          />
          {error ? (
            <p id="knowledge-urls-error" className="text-ember text-xs" role="alert">
              {error}
            </p>
          ) : null}
        </div>
        <DialogFooter className="flex-row justify-end gap-2 px-6 py-4">
          <Button type="button" variant="ghost" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={onAdd}
            className="bg-ember hover:bg-ember-mid focus-visible:ring-steel rounded-[9px] px-4 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
          >
            <Plus aria-hidden="true" />
            Add pages
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const SourceTable = ({
  isAdmin,
  sources,
  onSync,
  onToggle,
  onDelete,
  onSelect,
  onViewChanges,
}: {
  isAdmin: boolean
  sources: KbSourceRecord[]
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelect: (source: KbSourceRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => {
  if (sources.length === 0) {
    return (
      <section className="border-line bg-paper rounded-[8px] border px-6 py-12 text-center">
        <p className="text-ink text-sm font-bold">
          Add the public pages this site should answer from.
        </p>
      </section>
    )
  }
  return (
    <section className="border-line bg-paper overflow-hidden rounded-xl border">
      <div className="border-line flex flex-col gap-1 border-b px-5 py-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase">
            Content inputs
          </p>
          <h2 className="text-navy mt-1 text-lg font-extrabold tracking-[-0.025em]">Sources</h2>
          <p className="text-mute mt-1 text-xs">
            Websites and pages connected to this knowledge base.
          </p>
        </div>
        <span className="text-mute text-xs font-semibold">{sources.length} connected</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-sm">
          <thead className="bg-ice-2">
            <tr>
              <th className="text-ink px-5 py-3 text-xs font-bold">URL</th>
              <th className="text-ink px-5 py-3 text-xs font-bold">Status</th>
              <th className="text-ink px-5 py-3 text-xs font-bold">Pages</th>
              <th className="text-ink px-5 py-3 text-xs font-bold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                isAdmin={isAdmin}
                onSync={onSync}
                onToggle={onToggle}
                onDelete={onDelete}
                onSelect={onSelect}
                onViewChanges={onViewChanges}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

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
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <button
        type="button"
        onClick={handleViewChanges}
        className="text-steel hover:text-navy text-xs font-bold transition-[color,transform] duration-150 ease-out active:scale-[0.98] motion-safe:hover:-translate-y-px"
      >
        View changes
      </button>
      {isAdmin ? (
        <>
          <button
            type="button"
            onClick={handleSync}
            className="text-steel hover:text-navy inline-flex items-center gap-1.5 text-xs font-bold transition-[color,transform] duration-150 ease-out active:scale-[0.98] motion-safe:hover:-translate-y-px"
          >
            <RefreshCw aria-hidden="true" className="size-3.5" />
            Sync
          </button>
          <button
            type="button"
            onClick={handleToggle}
            className={`${source.enabled ? "text-ember" : "text-steel"} hover:text-navy text-xs font-bold transition-[color,transform] duration-150 ease-out active:scale-[0.98] motion-safe:hover:-translate-y-px`}
          >
            {source.enabled ? "Disable" : "Enable"}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="text-ember hover:text-ember-mid text-xs font-bold transition-[color,transform] duration-150 ease-out active:scale-[0.98] motion-safe:hover:-translate-y-px"
          >
            Delete
          </button>
        </>
      ) : null}
    </div>
  )
}

const SourceRow = ({
  source,
  isAdmin,
  onSync,
  onToggle,
  onDelete,
  onSelect,
  onViewChanges,
}: {
  source: KbSourceRecord
  isAdmin: boolean
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelect: (source: KbSourceRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => {
  const handleSelect = useCallback(() => onSelect(source), [onSelect, source])
  const pill = snapshotPill(source)
  return (
    <tr className="border-line hover:bg-ice/60 border-t transition-colors duration-150">
      <td className="px-5 py-3">
        <button
          type="button"
          onClick={handleSelect}
          className="text-steel hover:text-navy focus-visible:ring-steel font-mono text-xs transition-[color,transform] duration-150 ease-out focus-visible:ring-2 focus-visible:outline-none motion-safe:hover:-translate-y-px"
        >
          {source.start_url}
        </button>
      </td>
      <td className="text-mute px-5 py-3 text-xs">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-ink inline-flex items-center gap-1.5 font-semibold">
              <span
                className={`size-2 rounded-full ${source.status === "ready" ? "bg-[#29915E]" : "bg-ember"}`}
              />
              {sourceStatusLabel(source)}
            </span>
            {pill ? <span className={snapshotPillClass(source)}>{pill}</span> : null}
          </div>
          <SourceProgress source={source} />
        </div>
      </td>
      <td className="text-mute px-5 py-3 text-xs">{source.page_count}</td>
      <td className="px-5 py-3">
        <SourceRowActions
          source={source}
          isAdmin={isAdmin}
          onSync={onSync}
          onToggle={onToggle}
          onDelete={onDelete}
          onViewChanges={onViewChanges}
        />
      </td>
    </tr>
  )
}

const ingestIsActive = (source: KbSourceRecord) =>
  source.status !== "ready" &&
  (source.status === "running" ||
    source.stage === "discovering" ||
    source.stage === "processing" ||
    source.stage === "validating" ||
    source.stage === "promoting")

const sourceStatusLabel = (source: KbSourceRecord) => {
  if (source.status === "ready") {
    return "Ready"
  }
  if (source.status === "running") {
    return "Syncing"
  }
  return source.status.charAt(0).toUpperCase() + source.status.slice(1)
}

const ingestProgressLabel = (source: KbSourceRecord, discovered: number, embedded: number) => {
  if (source.stage === "discovering") {
    return "Discovering pages"
  }
  if (source.stage === "validating") {
    return "Validating snapshot"
  }
  if (source.stage === "promoting") {
    return "Promoting snapshot"
  }
  if (discovered > 0) {
    return `Processing ${embedded} of ${discovered} pages`
  }
  return source.status
}

const SourceProgress = ({ source }: { source: KbSourceRecord }) => {
  const discovered = source.pages_discovered ?? 0
  const embedded = source.pages_embedded ?? 0
  const failed = source.pages_failed ?? 0
  const active = ingestIsActive(source)
  if (!active && failed === 0) {
    return null
  }
  const label = ingestProgressLabel(source, discovered, embedded)
  return (
    <div className="flex flex-col gap-1">
      {active && discovered > 0 ? (
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
      {active ? <span>{label}</span> : null}
      {failed > 0 ? (
        <span className="bg-ice text-ember inline-flex w-fit rounded-[8px] px-2 py-0.5 text-[10px] font-bold">
          {failed} pages failed
        </span>
      ) : null}
    </div>
  )
}

const snapshotPill = (source: KbSourceRecord) => {
  const state = source.snapshot_state
  if (state === "live") {
    return "live"
  }
  if (state === "building") {
    return "building"
  }
  if (state === "validated") {
    return "validated"
  }
  if (state === "failed") {
    return source.snapshot_error_code ? `failed (${source.snapshot_error_code})` : "failed"
  }
  return null
}

const snapshotPillClass = (source: KbSourceRecord) => {
  if (source.snapshot_state === "live") {
    return "inline-flex items-center gap-1.5 rounded-full bg-[#E8F5EE] px-2.5 py-1 text-[10px] font-bold tracking-[0.06em] text-[#247A4D] uppercase dark:bg-[#163627] dark:text-[#8DDEAE]"
  }
  return "bg-ice-2 text-mute inline-flex w-fit rounded-full px-2.5 py-1 text-[10px] font-bold tracking-[0.06em] uppercase"
}

const PageTable = ({
  pages,
  selectedId,
  isAdmin,
  onSelect,
  onToggle,
}: {
  pages: KbPageRecord[]
  selectedId: string | null
  isAdmin: boolean
  onSelect: (page: KbPageRecord) => void
  onToggle: (page: KbPageRecord) => void
}) => {
  if (pages.length === 0) {
    return null
  }
  return (
    <section className="border-line bg-paper overflow-hidden rounded-xl border">
      <div className="border-line border-b px-5 py-5">
        <p className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase">
          Indexed content
        </p>
        <h2 className="text-navy mt-1 text-lg font-extrabold tracking-[-0.025em]">Pages</h2>
        <p className="text-mute mt-1 text-xs">
          Open a page to inspect the copy the assistant retrieves.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left text-sm">
          <thead className="bg-ice-2">
            <tr>
              <th className="text-ink px-5 py-3 text-xs font-bold">Title</th>
              <th className="text-ink px-5 py-3 text-xs font-bold">URL</th>
              <th className="text-ink px-5 py-3 text-xs font-bold">Status</th>
              {isAdmin ? <th className="text-ink px-5 py-3 text-xs font-bold">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {pages.map((page) => (
              <PageRow
                key={page.id}
                page={page}
                selected={page.id === selectedId}
                isAdmin={isAdmin}
                onSelect={onSelect}
                onToggle={onToggle}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

const PageRow = ({
  page,
  selected,
  isAdmin,
  onSelect,
  onToggle,
}: {
  page: KbPageRecord
  selected: boolean
  isAdmin: boolean
  onSelect: (page: KbPageRecord) => void
  onToggle: (page: KbPageRecord) => void
}) => {
  const handleSelect = useCallback(() => onSelect(page), [onSelect, page])
  const handleToggle = useCallback(() => onToggle(page), [onToggle, page])
  return (
    <tr
      className={`border-line hover:bg-ice/60 border-t transition-colors duration-150 ${selected ? "bg-ice-2" : "bg-paper"}`}
    >
      <td className="px-5 py-3">
        <button
          type="button"
          onClick={handleSelect}
          className="text-steel hover:text-navy focus-visible:ring-steel text-left text-sm font-semibold transition-[color,transform] duration-150 ease-out focus-visible:ring-2 focus-visible:outline-none motion-safe:hover:-translate-y-px"
        >
          {page.title}
        </button>
      </td>
      <td className="px-5 py-3">
        <button
          type="button"
          onClick={handleSelect}
          className="text-steel hover:text-navy focus-visible:ring-steel font-mono text-xs transition-[color,transform] duration-150 ease-out focus-visible:ring-2 focus-visible:outline-none motion-safe:hover:-translate-y-px"
        >
          {page.url}
        </button>
      </td>
      <td className="text-mute px-5 py-3 text-xs">{pageStatusLabel(page)}</td>
      {isAdmin ? (
        <td className="px-5 py-3">
          <button
            type="button"
            onClick={handleToggle}
            aria-label={page.enabled ? "Disable page" : "Enable page"}
            className={`${page.enabled ? "text-ember" : "text-steel"} hover:text-navy text-xs font-bold transition-[color,transform] duration-150 ease-out active:scale-[0.98] motion-safe:hover:-translate-y-px`}
          >
            {page.enabled ? "Disable" : "Enable"}
          </button>
        </td>
      ) : null}
    </tr>
  )
}

const pageStatusLabel = (page: KbPageRecord) => {
  if (page.processing_status === "failed") {
    return page.failure_reason ? `Skipped (${page.failure_reason})` : "Failed"
  }
  if (page.processing_status === "fetching") {
    return "Fetching"
  }
  if (page.processing_status === "extracting" || page.processing_status === "llm_extracting") {
    return "Extracting"
  }
  if (page.processing_status === "embedding") {
    return "Embedding"
  }
  if (page.processing_status === "unchanged") {
    return "Unchanged"
  }
  return page.enabled ? "Enabled" : "Disabled"
}

const IndexedCopyHeader = ({ detail }: { detail: KbPageDetail }) => (
  <div className="mb-3 flex flex-col gap-1">
    <p className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase">Page inspection</p>
    <h2 className="text-navy text-lg font-extrabold tracking-[-0.025em]">Source details</h2>
    {safeHttpUrl(detail.url) ? (
      <a
        href={safeHttpUrl(detail.url) ?? undefined}
        target="_blank"
        rel="noreferrer noopener"
        className="text-steel hover:text-navy decoration-steel/40 inline-flex w-fit items-center gap-1.5 font-mono text-xs underline underline-offset-4 transition-colors duration-150"
      >
        {detail.url}
        <ExternalLink aria-hidden="true" className="size-3.5" />
      </a>
    ) : (
      <p className="text-mute font-mono text-xs">{detail.url}</p>
    )}
  </div>
)

const IndexedCopyChunks = ({ detail }: { detail: KbPageDetail }) => {
  if (detail.chunks.length === 0) {
    return null
  }
  return (
    <Collapsible
      defaultOpen={false}
      className="border-line bg-paper overflow-hidden rounded-[12px] border shadow-[0_8px_24px_rgba(13,31,58,0.08)] dark:border-[#202833] dark:bg-[#07090C] dark:shadow-[0_8px_24px_rgba(0,0,0,0.24)]"
    >
      <CollapsibleTrigger className="group text-ink hover:bg-ice-2 px-5 py-4 transition-[background-color,border-color,transform] duration-[180ms] ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.997] dark:text-white dark:hover:bg-[#12171E]">
        <span className="flex items-center gap-3">
          <span className="bg-steel h-9 w-px rounded-full" aria-hidden="true" />
          <span className="flex flex-col gap-0.5">
            <span className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase dark:text-white/60">
              Retrieval units
            </span>
            <span className="text-navy text-sm font-extrabold dark:text-white">
              Retrieved answers{" "}
              <span className="text-mute font-mono text-xs dark:text-white/55">
                ({detail.chunks.length})
              </span>
            </span>
          </span>
        </span>
        <ChevronDown
          aria-hidden="true"
          className="text-mute size-5 transition-transform duration-200 ease-out group-aria-expanded:rotate-180 dark:text-white/65"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-line mt-0 flex flex-col gap-3 border-t px-5 pt-4 pb-5 dark:border-white/10">
        {detail.chunks.map((chunk) => (
          <article
            key={`${chunk.ordinal}-${chunk.heading}`}
            className="border-line bg-ice text-ink hover:border-steel/40 hover:bg-ice-2 rounded-[10px] border px-4 py-4 transition-[background-color,border-color] duration-150 dark:border-white/10 dark:bg-[#12171E] dark:text-white dark:hover:bg-[#18222D]"
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-navy text-sm font-bold dark:text-white">{chunk.heading}</h3>
              <span className="text-mute shrink-0 font-mono text-[10px] dark:text-white/55">
                #{chunk.ordinal + 1}
              </span>
            </div>
            <p className="text-ink mt-2 text-sm leading-6 whitespace-pre-wrap dark:text-white/80">
              {chunk.body}
            </p>
          </article>
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}

const IndexedCopy = ({ detail }: { detail: KbPageDetail | null }) => {
  if (detail === null) {
    return null
  }
  return (
    <section className="border-line bg-paper rounded-xl border p-5 lg:p-6">
      <IndexedCopyHeader detail={detail} />
      {detail.skip_reason ? (
        <p className="text-ember mt-4 text-sm">Skipped: {detail.skip_reason}</p>
      ) : null}
      <div className="flex flex-col gap-3">
        <Collapsible
          defaultOpen
          className="border-line bg-paper overflow-hidden rounded-[12px] border shadow-[0_8px_24px_rgba(13,31,58,0.08)] dark:border-[#202833] dark:bg-[#07090C] dark:shadow-[0_8px_24px_rgba(0,0,0,0.24)]"
        >
          <CollapsibleTrigger className="group text-ink hover:bg-ice-2 px-5 py-4 transition-[background-color,border-color,transform] duration-[180ms] ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.997] dark:text-white dark:hover:bg-[#12171E]">
            <span className="flex items-center gap-3">
              <span className="bg-steel h-9 w-px rounded-full" aria-hidden="true" />
              <span className="flex flex-col gap-0.5">
                <span className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase dark:text-white/60">
                  Raw page content
                </span>
                <span className="text-navy text-sm font-extrabold dark:text-white">
                  Indexed copy
                </span>
              </span>
            </span>
            <ChevronDown
              aria-hidden="true"
              className="text-mute size-5 transition-transform duration-200 ease-out group-aria-expanded:rotate-180 dark:text-white/65"
            />
          </CollapsibleTrigger>
          <CollapsibleContent className="border-line mt-0 border-t px-5 pt-4 pb-5 text-sm leading-6 dark:border-white/10">
            <p className="text-ink whitespace-pre-wrap dark:text-white/80">{detail.content_text}</p>
          </CollapsibleContent>
        </Collapsible>
        <IndexedCopyChunks detail={detail} />
      </div>
    </section>
  )
}
