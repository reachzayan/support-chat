"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- StaffHeader receives the composed site picker and add action. */

import { Plus } from "lucide-react"
import { useCallback, useState } from "react"

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
