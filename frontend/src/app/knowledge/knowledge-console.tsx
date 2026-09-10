"use client"

import { useCallback, useMemo, type ChangeEvent } from "react"

import type {
  KbPageDetail,
  KbPageRecord,
  KbSourceRecord,
  SiteRecord,
} from "@/components/admin/staff-api"
import { StaffHeader } from "@/components/admin/staff-nav"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { useKnowledgeState } from "./knowledge-state"
import { SnapshotDiffSheet } from "./snapshot-diff-sheet"

type KnowledgeConsoleProps = {
  isAdmin: boolean
  displayName: string
}

export const KnowledgeConsole = ({ isAdmin, displayName: _displayName }: KnowledgeConsoleProps) => {
  const state = useKnowledgeState(isAdmin)
  return (
    <div className="bg-ice flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0">
        <StaffHeader
          eyebrow="Workspace / Knowledge base"
          title="Knowledge base"
          description="Add the public pages this site should answer from."
        />
      </div>
      <div
        id="main-content"
        className="mx-auto grid min-h-0 w-full max-w-6xl flex-1 gap-5 overflow-y-auto px-5 py-6 lg:grid-cols-[260px_minmax(0,1fr)] lg:px-8 lg:py-8"
      >
        <section className="border-line bg-paper h-fit self-start rounded-[8px] border p-4 lg:sticky lg:top-6 lg:z-10">
          <p className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase">Site scope</p>
          <h2 className="text-navy mt-1 text-sm font-extrabold">Website sources</h2>
          <p className="text-mute mt-2 text-xs leading-5">
            The assistant retrieves from ingested pages for this brand only.
          </p>
          <SitePicker sites={state.sites} siteId={state.siteId} onSite={state.handleSite} />
          <div className="border-line mt-5 border-t pt-4">
            <p className="text-mute text-[10px] font-bold tracking-[0.12em] uppercase">Pages</p>
            <p className="text-navy mt-1 text-2xl font-extrabold">{state.pages.length}</p>
            <p className="text-mute text-xs">indexed for this site</p>
          </div>
        </section>
        <div className="flex min-w-0 flex-col gap-5">
          {isAdmin ? (
            <AddWebsite urls={state.urls} onUrls={state.handleUrls} onAdd={state.handleAdd} />
          ) : null}
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
    </div>
  )
}

const SitePicker = ({
  sites,
  siteId,
  onSite,
}: {
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
    <>
      <label
        className="text-ink mt-4 flex flex-col gap-1 text-xs font-bold"
        htmlFor="knowledge-site"
      >
        Site
      </label>
      <Select
        value={siteId || null}
        onValueChange={handleSiteChange}
        items={items}
        id="knowledge-site"
      >
        <SelectTrigger
          aria-label="Site"
          className="border-line bg-ice text-ink mt-2 h-11 w-full min-w-0 cursor-pointer rounded-[8px] border px-3 text-sm data-[size=default]:h-11"
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
    </>
  )
}

const AddWebsite = ({
  urls,
  onUrls,
  onAdd,
}: {
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onAdd: () => void
}) => {
  return (
    <section className="border-line bg-paper rounded-[8px] border p-5">
      <h2 className="text-navy text-sm font-extrabold">Add website</h2>
      <p className="text-mute mt-1 text-xs">Specific pages. One HTTPS URL per line.</p>
      <label className="text-ink mt-4 block text-xs font-bold" htmlFor="knowledge-urls">
        Page URLs
      </label>
      <textarea
        id="knowledge-urls"
        aria-label="Page URLs"
        value={urls}
        onChange={onUrls}
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 w-full rounded-[8px] border px-3 py-3 font-mono text-xs leading-6 outline-none focus-visible:ring-2"
        rows={3}
      />
      <button
        type="button"
        onClick={onAdd}
        className="bg-ember text-paper hover:bg-ember-mid focus-visible:ring-steel mt-4 rounded-[8px] px-4 py-2.5 text-sm font-bold focus-visible:ring-2 focus-visible:outline-none"
      >
        Add website
      </button>
    </section>
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
    <section className="border-line bg-paper overflow-hidden rounded-[8px] border">
      <div className="border-line border-b px-5 py-4">
        <h2 className="text-navy text-sm font-extrabold">Sources</h2>
      </div>
      <table className="w-full border-collapse text-left text-sm">
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
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={handleViewChanges}
        className="text-steel text-xs font-bold underline-offset-4 hover:underline"
      >
        View changes
      </button>
      {isAdmin ? (
        <>
          <button
            type="button"
            onClick={handleSync}
            className="text-steel text-xs font-bold underline-offset-4 hover:underline"
          >
            Sync
          </button>
          <button
            type="button"
            onClick={handleToggle}
            className={`${source.enabled ? "text-ember" : "text-steel"} text-xs font-bold underline-offset-4 hover:underline`}
          >
            {source.enabled ? "Disable" : "Enable"}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="text-ember text-xs font-bold underline-offset-4 hover:underline"
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
    <tr className="border-line border-t">
      <td className="px-5 py-3">
        <button
          type="button"
          onClick={handleSelect}
          className="text-steel focus-visible:ring-steel font-mono text-xs underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:outline-none"
        >
          {source.start_url}
        </button>
      </td>
      <td className="text-mute px-5 py-3 text-xs">
        <div className="flex flex-col gap-1">
          <span>{source.status}</span>
          {pill ? (
            <span className="bg-ice text-navy inline-flex w-fit rounded-[8px] px-2 py-0.5 text-[10px] font-bold">
              {pill}
            </span>
          ) : null}
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
  source.status === "running" ||
  source.stage === "discovering" ||
  source.stage === "processing" ||
  source.stage === "validating" ||
  source.stage === "promoting"

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
  if (!ingestIsActive(source) && failed === 0 && discovered === 0) {
    return null
  }
  const label = ingestProgressLabel(source, discovered, embedded)
  return (
    <div className="flex flex-col gap-1">
      {discovered > 0 ? (
        <progress
          aria-label="Ingestion progress"
          aria-valuemin={0}
          aria-valuemax={discovered}
          aria-valuenow={embedded}
          className="border-line h-1.5 w-full overflow-hidden rounded-[8px]"
          max={discovered}
          value={embedded}
        />
      ) : null}
      <span>{label}</span>
      {failed > 0 ? (
        <span className="bg-ice text-ember inline-flex w-fit rounded-[8px] px-2 py-0.5 text-[10px] font-bold">
          {failed} pages need review
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
    return "validated (pending)"
  }
  if (state === "failed") {
    return source.snapshot_error_code ? `failed (${source.snapshot_error_code})` : "failed"
  }
  return null
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
    <section className="border-line bg-paper overflow-hidden rounded-[8px] border">
      <div className="border-line border-b px-5 py-4">
        <h2 className="text-navy text-sm font-extrabold">Pages</h2>
        <p className="text-mute mt-1 text-xs">
          Open a page to read the copy the assistant retrieves.
        </p>
      </div>
      <table className="w-full border-collapse text-left text-sm">
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
    <tr className={`border-line border-t ${selected ? "bg-ice-2" : "bg-paper"}`}>
      <td className="px-5 py-3">
        <button
          type="button"
          onClick={handleSelect}
          className="text-steel focus-visible:ring-steel text-left text-sm font-semibold underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:outline-none"
        >
          {page.title}
        </button>
      </td>
      <td className="px-5 py-3">
        <button
          type="button"
          onClick={handleSelect}
          className="text-mute focus-visible:ring-steel font-mono text-xs underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:outline-none"
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
            className={`${page.enabled ? "text-ember" : "text-steel"} text-xs font-bold underline-offset-4 hover:underline`}
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

const IndexedCopy = ({ detail }: { detail: KbPageDetail | null }) => {
  if (detail === null) {
    return null
  }
  return (
    <section className="border-line bg-paper rounded-[8px] border p-5">
      <p className="text-mute text-[10px] font-bold tracking-[0.14em] uppercase">
        What the assistant uses
      </p>
      <h2 className="text-navy mt-1 text-sm font-extrabold">Indexed copy</h2>
      <p className="text-mute mt-1 font-mono text-xs">{detail.url}</p>
      {detail.skip_reason ? (
        <p className="text-ember mt-4 text-sm">Skipped: {detail.skip_reason}</p>
      ) : null}
      <div className="border-line bg-ice mt-4 rounded-[8px] border px-4 py-4">
        <p className="text-ink text-sm leading-6 whitespace-pre-wrap">{detail.content_text}</p>
      </div>
      {detail.chunks.length > 0 ? (
        <div className="mt-5 flex flex-col gap-3">
          <p className="text-mute text-[10px] font-bold tracking-[0.12em] uppercase">
            Retrieved as
          </p>
          {detail.chunks.map((chunk) => (
            <article
              key={`${chunk.ordinal}-${chunk.heading}`}
              className="border-line rounded-[8px] border px-4 py-3"
            >
              <h3 className="text-navy text-sm font-bold">{chunk.heading}</h3>
              <p className="text-ink mt-2 text-sm leading-6 whitespace-pre-wrap">{chunk.body}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  )
}
