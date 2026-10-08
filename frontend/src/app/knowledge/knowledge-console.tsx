"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- StaffHeader receives the composed site picker and add action. */

import { Plus } from "lucide-react"
import { useCallback, useState } from "react"

import { RetryError } from "@/components/admin/retry-error"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Button } from "@/components/ui/button"

import { AddKnowledgeDialog } from "./add-knowledge-dialog"
import { DetailPane } from "./knowledge-detail-pane"
import { SitePicker } from "./knowledge-site-picker"
import { SourcePane } from "./knowledge-source-pane"
import { useKnowledgeState } from "./knowledge-state"
import { SnapshotDiffSheet } from "./snapshot-diff-sheet"

type KnowledgeConsoleProps = {
  isAdmin: boolean
  displayName: string
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
  const showsEmptyState = state.sourcesLoaded && state.sources.length === 0
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
              {isAdmin && !showsEmptyState ? (
                <Button
                  type="button"
                  variant="default"
                  size="lg"
                  onClick={handleOpenAddKnowledge}
                  disabled={!state.siteId}
                  className="font-bold"
                >
                  <Plus data-icon="inline-start" aria-hidden="true" />
                  Add knowledge
                </Button>
              ) : null}
            </div>
          }
        />
        {state.loadError ? (
          <div className="px-5 py-3 lg:px-8">
            <RetryError text={state.loadError} onRetry={state.handleRetryLoad} className="mt-0" />
          </div>
        ) : null}
      </div>
      <KnowledgeLoadedCatalog isAdmin={isAdmin} state={state} onAdd={handleOpenAddKnowledge} />
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

const KnowledgeEmptyState = ({
  isAdmin,
  onAdd,
  disabled,
}: {
  isAdmin: boolean
  onAdd: () => void
  disabled: boolean
}) => (
  <div id="main-content" className="flex min-h-0 flex-1 items-center justify-center p-4 sm:p-6">
    <section className="border-line bg-paper w-full max-w-md rounded-xl border p-6 text-center sm:p-8">
      <h2 className="text-navy heading text-base">No knowledge sources yet</h2>
      <p className="text-mute mt-2 text-sm">
        Add a website or trusted text this site should answer from.
      </p>
      {isAdmin ? (
        <Button
          type="button"
          variant="default"
          size="lg"
          onClick={onAdd}
          disabled={disabled}
          className="mt-5 font-bold max-md:min-h-11 max-md:w-full"
        >
          <Plus data-icon="inline-start" aria-hidden="true" />
          Add knowledge
        </Button>
      ) : (
        <p className="text-mute mt-4 text-xs">An administrator can add sources.</p>
      )}
    </section>
  </div>
)

const KnowledgeLoadedCatalog = ({
  isAdmin,
  state,
  onAdd,
}: {
  isAdmin: boolean
  state: ReturnType<typeof useKnowledgeState>
  onAdd: () => void
}) => {
  if (state.loadError !== null && state.sites.length === 0) {
    return null
  }
  if (state.sourcesLoaded && state.sources.length === 0) {
    return <KnowledgeEmptyState isAdmin={isAdmin} onAdd={onAdd} disabled={!state.siteId} />
  }
  return (
    <>
      <KnowledgeMetrics
        sourceCount={state.sources.length}
        pageCount={state.pages.filter((page) => page.tab !== "general").length}
      />
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
          onSaveChunk={state.handleSaveChunk}
        />
      </div>
    </>
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
