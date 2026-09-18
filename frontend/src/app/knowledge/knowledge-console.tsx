"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-new-object-as-prop, react-perf/jsx-no-jsx-as-prop -- Retrieved-answer controls close over each immutable chunk record; motion props need inline transition objects; StaffHeader action takes composed controls. */

import { cn } from "cn"
import { ChevronDown, ExternalLink, FileText, Globe2, Plus, RefreshCw, Search } from "lucide-react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useCallback, useMemo, useState, type ChangeEvent, type KeyboardEvent } from "react"

import type {
  KbPageDetail,
  KbPageRecord,
  KbSourceRecord,
  SiteRecord,
} from "@/components/admin/staff-api"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogResizeSection,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { LinkButton, linkUnderlineClass } from "@/components/ui/link-button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { safeHttpUrl } from "@/lib/ua"

import { humanizeCode } from "./knowledge-format"
import { resolveKnowledgeSiteId, selectedSiteValue } from "./knowledge-site"
import { useKnowledgeState } from "./knowledge-state"
import { SnapshotDiffSheet } from "./snapshot-diff-sheet"

type KnowledgeConsoleProps = {
  isAdmin: boolean
  displayName: string
}

const EASE_OUT = [0.23, 1, 0.32, 1] as const
const FADE_UP = { duration: 0.18, ease: EASE_OUT }
const RAIL_SPRING = { type: "spring", stiffness: 500, damping: 42, mass: 0.6 } as const
const EMPTY_PAGES: KbPageRecord[] = []

const groupPagesBySource = (pages: KbPageRecord[]) => {
  const grouped: Record<string, KbPageRecord[]> = {}
  for (const page of pages) {
    const bucket = grouped[page.source_id] ?? []
    bucket.push(page)
    grouped[page.source_id] = bucket
  }
  return grouped
}

const sourceMatchesQuery = (
  source: KbSourceRecord,
  sourcePages: KbPageRecord[],
  needle: string,
) => {
  if (!needle) {
    return true
  }
  if (`${source.display_name ?? ""} ${source.start_url}`.toLocaleLowerCase().includes(needle)) {
    return true
  }
  return sourcePages.some((page) =>
    `${page.title} ${page.url}`.toLocaleLowerCase().includes(needle),
  )
}

const unitKindLabel = (kind: string) => {
  if (kind === "faq") return "FAQ"
  return kind.length > 0 ? `${kind[0].toLocaleUpperCase()}${kind.slice(1)}` : "Unit"
}

const originPagesLabel = (chunk: KbPageDetail["chunks"][number], pages: KbPageRecord[]) => {
  const origins = chunk.origin_urls ?? []
  if (origins.length < 2) {
    return null
  }
  const titles = origins.flatMap((url) => {
    const page = pages.find((item) => item.url === url && item.tab !== "general")
    return page?.title ? [page.title] : []
  })
  if (titles.length === 0) {
    return null
  }
  if (titles.length === 1) {
    return `Also on ${titles[0]}`
  }
  if (titles.length === 2) {
    return `Also on ${titles[0]} and ${titles[1]}`
  }
  return `Also on ${titles.slice(0, -1).join(", ")}, and ${titles[titles.length - 1]}`
}

// oxlint-disable-next-line eslint/max-lines-per-function -- This screen coordinates the existing knowledge state hook and its visible sections.
export const KnowledgeConsole = ({ isAdmin, displayName: _displayName }: KnowledgeConsoleProps) => {
  const state = useKnowledgeState(isAdmin)
  const { handleAdd } = state
  const [addKnowledgeOpen, setAddKnowledgeOpen] = useState(false)
  const selectedSite = state.sites.find((site) => site.id === state.siteId) ?? null
  const handleAddWebsite = useCallback(async () => {
    const added = await handleAdd()
    if (added) {
      setAddKnowledgeOpen(false)
    }
  }, [handleAdd])
  const handleOpenAddKnowledge = useCallback(() => setAddKnowledgeOpen(true), [])
  return (
    <div className="view-transition-enter bg-ice flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0">
        <StaffHeader
          title="Knowledge base"
          description="Add websites or trusted text this site should answer from."
          action={
            <div className="flex flex-wrap items-end gap-2">
              <SitePicker
                compact
                sites={state.sites}
                siteId={state.siteId}
                onSite={state.handleSite}
              />
              {isAdmin ? (
                <Button
                  type="button"
                  onClick={handleOpenAddKnowledge}
                  disabled={!state.siteId}
                  className="bg-ember hover:bg-ember-mid focus-visible:ring-steel h-10 rounded-[9px] px-4 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
                >
                  <Plus aria-hidden="true" />
                  Add knowledge
                </Button>
              ) : null}
            </div>
          }
        />
        <KnowledgeMetrics
          sourceCount={state.sources.length}
          pageCount={state.pages.filter((page) => page.tab !== "general").length}
        />
      </div>
      <div id="main-content" className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        <SourcePane
          isAdmin={isAdmin}
          sources={state.sources}
          pages={state.pages}
          selectedSourceId={state.sourceId}
          selectedPageId={state.pageDetail?.id ?? null}
          onSync={state.handleSync}
          onToggle={state.handleToggleSource}
          onDelete={state.handleDelete}
          onSelect={state.handleSelectSource}
          onSelectPage={state.handleSelectPage}
          onViewChanges={state.handleViewChanges}
        />
        <DetailPane
          detail={state.pageDetail}
          pages={state.pages}
          hasSource={state.sources.length > 0}
          isAdmin={isAdmin}
          pendingIds={state.chunkPendingIds}
          errors={state.chunkErrors}
          notice={state.chunkNotice}
          onTogglePage={state.handleTogglePage}
          onRetryPage={state.handleRetryPage}
          onToggleChunk={state.handleToggleChunk}
        />
      </div>
      <SnapshotDiffSheet
        open={state.diffSource !== null}
        onOpenChange={state.handleDiffOpen}
        diff={state.diff}
        status={state.diffStatus}
        canRollback={isAdmin && state.canRollback}
        rollbackBusy={state.rollbackBusy}
        onRollback={state.handleRollback}
        progress={state.detailProgress}
      />
      {isAdmin ? (
        <AddKnowledgeDialog
          open={addKnowledgeOpen}
          onOpenChange={setAddKnowledgeOpen}
          siteName={selectedSite?.name ?? "this website"}
          urls={state.urls}
          onUrls={state.handleUrls}
          onAdd={handleAddWebsite}
          onAddText={state.handleAddText}
          busy={state.addBusy}
          error={state.addError}
        />
      ) : null}
    </div>
  )
}

const KnowledgeMetrics = ({
  sourceCount,
  pageCount,
}: {
  sourceCount: number
  pageCount: number
}) => (
  <div className="border-line flex items-end gap-8 border-b px-5 py-3 lg:px-8">
    <OverviewMetric label="Sources" value={sourceCount} />
    <OverviewMetric label="Indexed pages" value={pageCount} />
  </div>
)

const OverviewMetric = ({ label, value }: { label: string; value: number }) => (
  <div>
    <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">{label}</p>
    <p className="text-navy heading mt-1 text-xl tabular-nums">{value}</p>
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
  const items = useMemo(
    () => Object.fromEntries(sites.map((site) => [site.id, site.name])),
    [sites],
  )
  const handleSiteChange = useCallback(
    (value: unknown) => {
      const selected = selectedSiteValue(value)
      if (selected === null) {
        return
      }
      const nextId = resolveKnowledgeSiteId(sites, selected, siteId)
      if (nextId === null) {
        return
      }
      onSite(nextId)
    },
    [onSite, siteId, sites],
  )
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${compact ? "w-44" : "sm:w-56"}`}>
      <label
        className={`${compact ? "sr-only" : "text-mute text-[10px] font-semibold tracking-[0.12em] uppercase"}`}
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
            {sites.map((site) => (
              <SelectItem key={site.id} value={site.id}>
                {site.name}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}

const AddKnowledgeDialog = ({
  open,
  onOpenChange,
  siteName,
  urls,
  onUrls,
  onAdd,
  onAddText,
  busy,
  error,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteName: string
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onAdd: () => void
  onAddText: (title: string, body: string) => Promise<boolean>
  busy: boolean
  error: string | null
}) => {
  const [kind, setKind] = useState<"website" | "text">("website")
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const handleCancel = useCallback(() => onOpenChange(false), [onOpenChange])
  const showWebsite = useCallback(() => setKind("website"), [])
  const showText = useCallback(() => setKind("text"), [])
  const handleTextSubmit = useCallback(async () => {
    if (await onAddText(title, body)) {
      setTitle("")
      setBody("")
      onOpenChange(false)
    }
  }, [body, onAddText, onOpenChange, title])
  const handleTextKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault()
        void handleTextSubmit()
      }
    },
    [handleTextSubmit],
  )
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl gap-0 p-0">
        <AddKnowledgeHeader siteName={siteName} />
        <DialogResizeSection className="flex flex-col gap-3 px-6 py-6">
          <KnowledgeTypePicker kind={kind} onWebsite={showWebsite} onText={showText} />
          {kind === "website" ? (
            <WebsiteFields urls={urls} onUrls={onUrls} error={error} />
          ) : (
            <TextFields
              title={title}
              body={body}
              onTitle={setTitle}
              onBody={setBody}
              onKeyDown={handleTextKeyDown}
              error={error}
            />
          )}
          <FieldError id="knowledge-add-error">{error ?? undefined}</FieldError>
        </DialogResizeSection>
        <AddKnowledgeFooter
          kind={kind}
          busy={busy}
          onCancel={handleCancel}
          onWebsite={onAdd}
          onText={handleTextSubmit}
        />
      </DialogContent>
    </Dialog>
  )
}

const AddKnowledgeHeader = ({ siteName }: { siteName: string }) => (
  <DialogHeader className="bg-ice/70 px-6 py-5">
    <div className="bg-ember/10 text-ember mb-2 flex size-10 items-center justify-center rounded-[10px]">
      <Plus aria-hidden="true" className="size-5" strokeWidth={2.2} />
    </div>
    <DialogTitle className="text-lg">Add knowledge</DialogTitle>
    <DialogDescription className="max-w-md leading-5">
      Connect public pages or add trusted text for {siteName}.
    </DialogDescription>
  </DialogHeader>
)

const KnowledgeTypePicker = ({
  kind,
  onWebsite,
  onText,
}: {
  kind: "website" | "text"
  onWebsite: () => void
  onText: () => void
}) => (
  <div className="bg-ice-2 flex w-fit gap-1 rounded-[9px] p-1" aria-label="Knowledge type">
    <button
      type="button"
      aria-pressed={kind === "website"}
      onClick={onWebsite}
      className={`rounded-[7px] px-3 py-2 text-xs font-bold ${kind === "website" ? "bg-paper text-navy shadow-sm" : "text-mute"}`}
    >
      Website
    </button>
    <button
      type="button"
      aria-pressed={kind === "text"}
      onClick={onText}
      className={`rounded-[7px] px-3 py-2 text-xs font-bold ${kind === "text" ? "bg-paper text-navy shadow-sm" : "text-mute"}`}
    >
      Plain text
    </button>
  </div>
)

const AddKnowledgeFooter = ({
  kind,
  busy,
  onCancel,
  onWebsite,
  onText,
}: {
  kind: "website" | "text"
  busy: boolean
  onCancel: () => void
  onWebsite: () => void
  onText: () => void
}) => (
  <DialogFooter className="flex-row justify-end gap-2 px-6 py-4">
    <Button type="button" variant="ghost" onClick={onCancel}>
      Cancel
    </Button>
    <Button
      type="button"
      onClick={kind === "website" ? onWebsite : onText}
      disabled={busy}
      className="bg-ember hover:bg-ember-mid focus-visible:ring-steel rounded-[9px] px-4 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none"
    >
      <Plus aria-hidden="true" />
      {busy ? "Adding…" : kind === "website" ? "Add pages" : "Add text"}
    </Button>
  </DialogFooter>
)

const WebsiteFields = ({
  urls,
  onUrls,
  error,
}: {
  urls: string
  onUrls: (event: ChangeEvent<HTMLTextAreaElement>) => void
  error: string | null
}) => (
  <div className="flex flex-col gap-3">
    <div>
      <label className="text-ink block text-sm font-medium" htmlFor="knowledge-urls">
        Website URL
      </label>
      <p className="text-mute mt-1 text-xs">
        One HTTPS URL crawls the site. Additional lines index only those pages.
      </p>
    </div>
    <Textarea
      id="knowledge-urls"
      name="pageUrls"
      autoComplete="off"
      value={urls}
      onChange={onUrls}
      placeholder="https://example.com/services"
      className="border-line bg-ice text-ink focus-visible:ring-steel min-h-24 w-full resize-y rounded-[9px] border px-3 py-3 font-mono text-base leading-6 outline-none focus-visible:ring-2 sm:text-sm"
      rows={3}
      aria-invalid={error ? "true" : undefined}
      aria-describedby="knowledge-add-error"
    />
  </div>
)

const TextFields = ({
  title,
  body,
  onTitle,
  onBody,
  onKeyDown,
  error,
}: {
  title: string
  body: string
  onTitle: (value: string) => void
  onBody: (value: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  error: string | null
}) => (
  <div className="flex flex-col gap-4">
    <div>
      <label className="text-ink block text-sm font-medium" htmlFor="knowledge-title">
        Title
      </label>
      <input
        id="knowledge-title"
        value={title}
        onChange={(event) => onTitle(event.target.value)}
        maxLength={300}
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 h-10 w-full rounded-[9px] border px-3 text-base outline-none focus-visible:ring-2 sm:text-sm"
        placeholder="Collections policy"
        aria-invalid={error ? "true" : undefined}
        aria-describedby="knowledge-add-error"
      />
    </div>
    <div>
      <label className="text-ink block text-sm font-medium" htmlFor="knowledge-content">
        Content
      </label>
      <p className="text-mute mt-1 text-xs">
        Add verified information only. Do not include sensitive personal data.
      </p>
      <Textarea
        id="knowledge-content"
        value={body}
        onChange={(event) => onBody(event.target.value)}
        onKeyDown={onKeyDown}
        maxLength={40_000}
        rows={9}
        className="border-line bg-ice text-ink focus-visible:ring-steel mt-2 min-h-48 w-full resize-y rounded-[9px] border px-3 py-3 text-base leading-6 outline-none focus-visible:ring-2 sm:text-sm"
        placeholder="Paste the trusted information the assistant may use…"
        aria-invalid={error ? "true" : undefined}
        aria-describedby="knowledge-add-error"
      />
    </div>
  </div>
)

const PaneSearch = ({
  id,
  label,
  value,
  onQuery,
  placeholder,
}: {
  id: string
  label: string
  value: string
  onQuery: (value: string) => void
  placeholder: string
}) => (
  <label htmlFor={id} className="relative block">
    <span className="sr-only">{label}</span>
    <Search aria-hidden="true" className="text-mute absolute top-2.5 left-3 size-3.5" />
    <Input
      id={id}
      type="search"
      aria-label={label}
      value={value}
      onChange={(event) => onQuery(event.target.value)}
      placeholder={placeholder}
      className="border-line bg-ice-2/60 text-ink placeholder:text-mute h-9 rounded-[9px] border pr-3 pl-9 text-xs"
    />
  </label>
)

const SourcePane = ({
  isAdmin,
  sources,
  pages,
  selectedSourceId,
  selectedPageId,
  onSync,
  onToggle,
  onDelete,
  onSelect,
  onSelectPage,
  onViewChanges,
}: {
  isAdmin: boolean
  sources: KbSourceRecord[]
  pages: KbPageRecord[]
  selectedSourceId: string | null
  selectedPageId: string | null
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelect: (source: KbSourceRecord) => void
  onSelectPage: (page: KbPageRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => {
  const [query, setQuery] = useState("")
  const pagesBySource = useMemo(() => groupPagesBySource(pages), [pages])
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return sources.filter((source) =>
      sourceMatchesQuery(source, pagesBySource[source.id] ?? EMPTY_PAGES, needle),
    )
  }, [pagesBySource, query, sources])
  return (
    <section className="border-line bg-paper flex min-h-0 w-full flex-col border-b lg:w-[28rem] lg:shrink-0 lg:border-r lg:border-b-0">
      <div className="flex h-14 items-center justify-between gap-3 px-5">
        <h2 className="text-navy heading text-sm">Sources</h2>
        <span className="text-mute text-xs font-semibold">{sources.length} connected</span>
      </div>
      {sources.length === 0 ? (
        <div className="flex flex-1 items-center justify-center px-6 py-12 text-center">
          <p className="text-ink heading text-sm">
            Add a website or trusted text this site should answer from.
          </p>
        </div>
      ) : (
        <>
          <div className="px-4 pb-3">
            <PaneSearch
              id="knowledge-source-search"
              label="Search sources"
              value={query}
              onQuery={setQuery}
              placeholder="Search sources"
            />
          </div>
          <ScrollArea className="min-h-0 flex-1">
            <SourceList
              sources={filtered}
              pagesBySource={pagesBySource}
              selectedSourceId={selectedSourceId}
              selectedPageId={selectedPageId}
              isAdmin={isAdmin}
              onSelect={onSelect}
              onSync={onSync}
              onToggle={onToggle}
              onDelete={onDelete}
              onSelectPage={onSelectPage}
              onViewChanges={onViewChanges}
            />
          </ScrollArea>
        </>
      )}
    </section>
  )
}

const SourceList = ({
  sources,
  pagesBySource,
  selectedSourceId,
  selectedPageId,
  isAdmin,
  onSelect,
  onSync,
  onToggle,
  onDelete,
  onSelectPage,
  onViewChanges,
}: {
  sources: KbSourceRecord[]
  pagesBySource: Record<string, KbPageRecord[]>
  selectedSourceId: string | null
  selectedPageId: string | null
  isAdmin: boolean
  onSelect: (source: KbSourceRecord) => void
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelectPage: (page: KbPageRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => (
  <ul className="px-2 pb-4">
    {sources.map((source) => (
      <SourceRow
        key={source.id}
        source={source}
        pages={pagesBySource[source.id] ?? EMPTY_PAGES}
        selected={source.id === selectedSourceId}
        selectedPageId={selectedPageId}
        isAdmin={isAdmin}
        onSelect={onSelect}
        onSync={onSync}
        onToggle={onToggle}
        onDelete={onDelete}
        onSelectPage={onSelectPage}
        onViewChanges={onViewChanges}
      />
    ))}
  </ul>
)

const ingestIsActive = (source: KbSourceRecord) =>
  source.status !== "ready" &&
  (source.status === "running" ||
    source.stage === "discovering" ||
    source.stage === "processing" ||
    source.stage === "validating" ||
    source.stage === "promoting")

const sourceIsSyncing = (source: KbSourceRecord) =>
  ingestIsActive(source) || source.status === "running" || source.status === "queued"

const sourceSyncActionLabel = (source: KbSourceRecord) => {
  if (source.source_kind === "text") return "Reprocess"
  if (source.status === "failed" || (source.pages_failed ?? 0) > 0) return "Retry crawl"
  return "Sync"
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
  const syncing = sourceIsSyncing(source)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <LinkButton type="button" onClick={handleViewChanges}>
        View progress
      </LinkButton>
      {isAdmin ? (
        <>
          <LinkButton type="button" onClick={handleSync} disabled={syncing}>
            <RefreshCw aria-hidden="true" className={cn("size-3.5", syncing && "animate-spin")} />
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
      <button
        type="button"
        onClick={handleSelect}
        aria-current={selected ? "true" : undefined}
        aria-label={page.title}
        className="focus-visible:ring-steel w-full rounded-[6px] px-1 py-1.5 text-left focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="block max-w-full truncate">
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
      </button>
    </li>
  )
}

const SourceRowTrigger = ({ source }: { source: KbSourceRecord }) => (
  <CollapsibleTrigger className="group w-full gap-2">
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
}: {
  source: KbSourceRecord
  pages: KbPageRecord[]
  selectedPageId: string | null
  isAdmin: boolean
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelectPage: (page: KbPageRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => {
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
        <SourceRowTrigger source={source} />
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

const SourceRow = ({
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
}: {
  source: KbSourceRecord
  pages: KbPageRecord[]
  selected: boolean
  selectedPageId: string | null
  isAdmin: boolean
  onSelect: (source: KbSourceRecord) => void
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelectPage: (page: KbPageRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}) => {
  const handleSelect = useCallback(() => onSelect(source), [onSelect, source])
  return (
    <li className="px-1 py-0.5">
      {/* oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- Nested Sync/page buttons cannot live inside another button; the source title is the keyboard control. */}
      <div
        onClick={handleSelect}
        className={cn(
          "relative cursor-pointer rounded-[10px] px-3 py-3 transition-colors duration-150",
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
          />
        </Collapsible>
      </div>
    </li>
  )
}

const sourceStatusLabel = (source: KbSourceRecord) => {
  if (ingestIsActive(source) || source.status === "running") {
    return "Syncing"
  }
  if (source.status === "queued") {
    return "Queued"
  }
  if (source.status === "failed") {
    const reason = sourceFailureReason(source)
    if (source.snapshot_state === "live") {
      return reason ? `Sync failed — live unchanged (${reason})` : "Sync failed — live unchanged"
    }
    return reason ? `Failed — ${reason}` : "Failed"
  }
  return "Ready"
}

const sourceFailureReason = (source: KbSourceRecord) => {
  const rules = source.validation_errors ?? []
  if (rules.length > 0) {
    return rules.map(humanizeCode).join(", ")
  }
  const code = source.error_code ?? source.snapshot_error_code
  return code ? humanizeCode(code) : null
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

const sourceNextStep = (source: KbSourceRecord) => {
  const rules = source.validation_errors ?? []
  if (rules.length > 0) {
    return "Live answers were left unchanged. Review the failed rule, then retry the crawl."
  }
  if ((source.pages_failed ?? 0) > 0) {
    return "Open a failed page and retry it, or retry the crawl."
  }
  if (source.status === "failed") {
    return "Review crawl activity, then retry the crawl."
  }
  return null
}

const IngestProgressBar = ({
  source,
  discovered,
  embedded,
}: {
  source: KbSourceRecord
  discovered: number
  embedded: number
}) => {
  return (
    <>
      {discovered > 0 ? (
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
      <span>{ingestProgressLabel(source, discovered, embedded)}</span>
    </>
  )
}

const SourceFailureHints = ({ failed, nextStep }: { failed: number; nextStep: string | null }) => (
  <>
    {failed > 0 ? (
      <span className="text-ember text-[10px] font-bold">
        {failed} {failed === 1 ? "page" : "pages"} failed
      </span>
    ) : null}
    {nextStep !== null ? <span className="text-mute">{nextStep}</span> : null}
  </>
)

const SourceProgress = ({ source }: { source: KbSourceRecord }) => {
  const discovered = source.pages_discovered ?? 0
  const embedded = source.pages_embedded ?? 0
  const failed = source.pages_failed ?? 0
  const active = ingestIsActive(source)
  const nextStep = active ? null : sourceNextStep(source)
  if (!active && failed === 0 && nextStep === null) {
    return null
  }
  return (
    <div className="flex flex-col gap-1">
      {active ? (
        <IngestProgressBar source={source} discovered={discovered} embedded={embedded} />
      ) : null}
      <SourceFailureHints failed={failed} nextStep={nextStep} />
    </div>
  )
}

const DetailPane = ({
  detail,
  pages,
  hasSource,
  isAdmin,
  pendingIds,
  errors,
  notice,
  onTogglePage,
  onRetryPage,
  onToggleChunk,
}: {
  detail: KbPageDetail | null
  pages: KbPageRecord[]
  hasSource: boolean
  isAdmin: boolean
  pendingIds: string[]
  errors: Record<string, string>
  notice: string
  onTogglePage: (page: KbPageRecord) => void
  onRetryPage: (page: KbPageRecord) => void
  onToggleChunk: (pageId: string, chunk: KbPageDetail["chunks"][number]) => Promise<void>
}) => (
  <section className="bg-paper flex min-h-0 min-w-0 flex-1 flex-col">
    <div className="flex h-14 items-center px-5">
      <h2 className="text-navy heading text-sm">Retrieved answers</h2>
    </div>
    <ScrollArea className="min-h-0 flex-1">
      {detail ? (
        <PageInspection
          detail={detail}
          pages={pages}
          isAdmin={isAdmin}
          pendingIds={pendingIds}
          errors={errors}
          notice={notice}
          onTogglePage={onTogglePage}
          onRetryPage={onRetryPage}
          onToggle={onToggleChunk}
        />
      ) : (
        <p className="text-mute px-5 py-8 text-sm">
          {hasSource
            ? "Select a page to inspect retrieved answers."
            : "Add a source to get started."}
        </p>
      )}
    </ScrollArea>
  </section>
)

const PageRowActions = ({
  page,
  onToggle,
  onRetry,
}: {
  page: KbPageRecord
  onToggle: (page: KbPageRecord) => void
  onRetry: (page: KbPageRecord) => void
}) => {
  const handleToggle = useCallback(() => onToggle(page), [onToggle, page])
  const handleRetry = useCallback(() => onRetry(page), [onRetry, page])
  return (
    <div className="flex items-center gap-3">
      {page.processing_status === "failed" ? (
        <LinkButton type="button" onClick={handleRetry}>
          Retry page
        </LinkButton>
      ) : null}
      <LinkButton
        type="button"
        variant={page.enabled ? "emphasis" : "default"}
        onClick={handleToggle}
        aria-label={page.enabled ? "Disable page" : "Enable page"}
      >
        {page.enabled ? "Disable" : "Enable"}
      </LinkButton>
    </div>
  )
}

const InspectionHeader = ({
  detail,
  isAdmin,
  onTogglePage,
  onRetryPage,
}: {
  detail: KbPageDetail
  isAdmin: boolean
  onTogglePage: (page: KbPageRecord) => void
  onRetryPage: (page: KbPageRecord) => void
}) => {
  const href = safeHttpUrl(detail.url)
  return (
    <div className="mb-4 flex flex-col gap-1">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
            {detail.tab === "general" ? "Shared answers" : "Page inspection"}
          </p>
          <h3 className="text-navy heading text-base">{detail.title}</h3>
        </div>
        {isAdmin && detail.tab !== "general" ? (
          <PageRowActions page={detail} onToggle={onTogglePage} onRetry={onRetryPage} />
        ) : null}
      </div>
      {href ? (
        <a
          href={href}
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
      <p className="text-mute mt-2 text-xs font-semibold">
        {detail.chunks.filter((chunk) => chunk.enabled).length} of {detail.chunks.length} answers
        enabled
      </p>
    </div>
  )
}

const InspectionNotices = ({ detail, notice }: { detail: KbPageDetail; notice: string }) => (
  <>
    {detail.skip_reason ? (
      <p className="text-ember mt-2 text-sm">Skipped: {humanizeCode(detail.skip_reason)}</p>
    ) : null}
    {detail.failure_reason && detail.failure_reason !== detail.skip_reason ? (
      <p className="text-ember mt-2 text-sm">Failed: {humanizeCode(detail.failure_reason)}</p>
    ) : null}
    {notice ? <output className="text-ember mt-3 block text-sm">{notice}</output> : null}
  </>
)

const AnswerUnit = ({
  pageId,
  pages,
  chunk,
  isAdmin,
  pending,
  error,
  onToggle,
}: {
  pageId: string
  pages: KbPageRecord[]
  chunk: KbPageDetail["chunks"][number]
  isAdmin: boolean
  pending: boolean
  error: string | undefined
  onToggle: (pageId: string, chunk: KbPageDetail["chunks"][number]) => Promise<void>
}) => {
  const originLabel = originPagesLabel(chunk, pages)
  return (
    <article className={cn("py-4 transition-opacity duration-150", !chunk.enabled && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-navy heading text-sm">{chunk.heading}</h4>
        <div className="flex shrink-0 items-center gap-2">
          <Badge className="bg-ice-2 text-steel">{unitKindLabel(chunk.kind)}</Badge>
          <Badge className={chunk.enabled ? "bg-[#E8F5EE] text-[#247A4D]" : "bg-ice-2 text-mute"}>
            {chunk.enabled ? "Enabled" : "Disabled"}
          </Badge>
          <span className="text-mute font-mono text-[10px]">#{chunk.ordinal + 1}</span>
        </div>
      </div>
      <p className="text-ink mt-2 text-sm leading-6 whitespace-pre-wrap">{chunk.body}</p>
      {originLabel ? <p className="text-mute mt-2 text-xs">{originLabel}</p> : null}
      {isAdmin ? (
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-mute text-xs font-bold">Include in answers</span>
          <Switch
            aria-label={`Include ${chunk.heading} in answers`}
            checked={chunk.enabled}
            disabled={pending}
            onCheckedChange={() => void onToggle(pageId, chunk)}
          />
        </div>
      ) : null}
      {error ? (
        <p className="text-ember mt-3 text-xs" role="alert">
          {error}{" "}
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => void onToggle(pageId, chunk)}
          >
            Retry
          </button>
        </p>
      ) : null}
    </article>
  )
}

const PageInspection = ({
  detail,
  pages,
  isAdmin,
  pendingIds,
  errors,
  notice,
  onTogglePage,
  onRetryPage,
  onToggle,
}: {
  detail: KbPageDetail
  pages: KbPageRecord[]
  isAdmin: boolean
  pendingIds: string[]
  errors: Record<string, string>
  notice: string
  onTogglePage: (page: KbPageRecord) => void
  onRetryPage: (page: KbPageRecord) => void
  onToggle: (pageId: string, chunk: KbPageDetail["chunks"][number]) => Promise<void>
}) => {
  const reducedMotion = useReducedMotion()
  return (
    <AnimatePresence mode="wait">
      <motion.section
        key={detail.id}
        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reducedMotion ? undefined : { opacity: 0, y: 6 }}
        transition={FADE_UP}
        className="px-5 pt-2 pb-8"
      >
        <InspectionHeader
          detail={detail}
          isAdmin={isAdmin}
          onTogglePage={onTogglePage}
          onRetryPage={onRetryPage}
        />
        <InspectionNotices detail={detail} notice={notice} />
        {detail.chunks.length === 0 ? (
          <p className="text-mute mt-4 text-sm">No retrieved answers on this page yet.</p>
        ) : (
          <div className="divide-line mt-2 divide-y">
            {detail.chunks.map((chunk) => (
              <AnswerUnit
                key={chunk.id}
                pageId={detail.id}
                pages={pages}
                chunk={chunk}
                isAdmin={isAdmin}
                pending={pendingIds.includes(chunk.id)}
                error={errors[chunk.id]}
                onToggle={onToggle}
              />
            ))}
          </div>
        )}
      </motion.section>
    </AnimatePresence>
  )
}
