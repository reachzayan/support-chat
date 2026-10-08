"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-function-as-prop -- StaffHeader actions and dialog callbacks use the current library state. */

import { History, Plus, Upload } from "lucide-react"
import { useState } from "react"

import { useOptionalAdminUser } from "@/components/admin/admin-shell"
import { StaffHeader } from "@/components/admin/staff-nav"
import {
  AlertDialog,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

import { ImportDialog } from "./canned-import-dialog"
import { ImportHistoryDialog } from "./canned-import-history"
import { DeleteDialog, ResponseForm } from "./canned-response-dialogs"
import {
  CannedResponsesSkeleton,
  CannedScrollPane,
  EmptyState,
  ResponseCard,
  ResponseRow,
} from "./canned-response-list"
import {
  botOptions,
  CannedResponseSelect,
  scopeOptions,
  statusOptions,
} from "./canned-response-select"
import { useCannedResponsesState } from "./use-canned-responses-state"

// oxlint-disable-next-line eslint/max-lines-per-function, eslint/complexity -- Compose the library controls, list, and edit dialogs.
export const CannedResponsesConsole = () => {
  const state = useCannedResponsesState()
  const staff = useOptionalAdminUser()
  const [importOpen, setImportOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  if (state.loadError) {
    return (
      <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col">
        <StaffHeader
          title="Canned responses"
          description="Reuse approved specialist wording across chats."
        />
        <main id="main-content" className="flex flex-1 items-center justify-center p-6">
          <div className="border-line bg-paper w-full max-w-md rounded-xl border p-6 text-center">
            <p className="text-navy heading text-base">Canned responses could not be loaded</p>
            <p className="text-mute mt-2 text-sm">Check your connection and try again.</p>
            <Button
              variant="default"
              size="lg"
              className="mt-5 font-bold"
              onClick={() => void state.load()}
            >
              Retry
            </Button>
          </div>
        </main>
      </div>
    )
  }

  if (state.records === null) {
    return (
      <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <StaffHeader
          title="Canned responses"
          description="Reuse approved specialist wording across chats."
        />
        {state.showLoading ? <CannedResponsesSkeleton /> : null}
      </div>
    )
  }

  const records = state.records

  return (
    <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <StaffHeader
        title="Canned responses"
        description="Reuse approved specialist wording across chats."
        action={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button variant="outline" size="lg" onClick={() => setHistoryOpen(true)}>
              <History data-icon="inline-start" aria-hidden="true" /> Upload history
            </Button>
            {staff?.is_admin ? (
              <Button variant="outline" size="lg" onClick={() => setImportOpen(true)}>
                <Upload data-icon="inline-start" aria-hidden="true" /> Import CSV
              </Button>
            ) : null}
            <Button variant="default" size="lg" className="font-bold" onClick={state.openCreate}>
              <Plus data-icon="inline-start" aria-hidden="true" /> Add response
            </Button>
          </div>
        }
      />
      <main
        id="main-content"
        className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-hidden px-5 py-6 lg:px-8 lg:py-8"
      >
        <section className="border-line bg-paper shrink-0 rounded-xl border p-4 sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[minmax(15rem,1fr)_10rem_11rem]">
            <div className="text-ink flex flex-col gap-1.5 text-xs font-medium">
              <span>Scope</span>
              <CannedResponseSelect
                value={state.scope}
                onValueChange={state.selectScope}
                items={scopeOptions(state.sites)}
                label="Scope"
              />
            </div>
            <div className="text-ink flex flex-col gap-1.5 text-xs font-medium">
              <span>Status</span>
              <CannedResponseSelect
                value={state.status}
                onValueChange={state.updateStatus}
                items={statusOptions}
                label="Status"
              />
            </div>
            <div className="text-ink flex flex-col gap-1.5 text-xs font-medium">
              <span>Assistant</span>
              <CannedResponseSelect
                value={state.bot}
                onValueChange={state.updateBot}
                items={botOptions}
                label="Assistant"
              />
            </div>
          </div>
          <p className="text-mute mt-4 text-xs" aria-live="polite">
            {state.summary}
          </p>
          {state.scope !== "general" ? (
            <p className="text-mute mt-1 text-xs">
              Matching website shortcuts override General responses and remain overridden while
              disabled.
            </p>
          ) : null}
        </section>

        {state.visible.length === 0 ? (
          state.query.trim() || state.status !== "all" || state.bot !== "all" ? (
            <section className="border-line bg-paper rounded-xl border p-8 text-center">
              <p className="text-navy heading text-base">
                {state.query.trim()
                  ? `No responses match “${state.query.trim()}”`
                  : `No ${state.status} responses in this scope`}
              </p>
              <p className="text-mute mx-auto mt-2 max-w-md text-sm">
                Try fewer words, another shortcut, or clear the current search filters.
              </p>
              <Button
                type="button"
                variant="outline"
                className="mt-5"
                onClick={state.clearSearchFilters}
              >
                Clear search filters
              </Button>
            </section>
          ) : (
            <EmptyState scope={state.scope} sites={state.sites} onAdd={state.openCreate} />
          )
        ) : (
          <section className="border-line bg-paper flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border">
            <CannedScrollPane
              className="hidden min-h-0 flex-1 overflow-x-scroll overflow-y-auto overscroll-none md:block"
              hasMore={state.hasMore}
              loadedCount={state.visible.length}
              onLoadMore={state.loadMore}
            >
              <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                <thead className="bg-ice-2 text-ink sticky top-0 z-10 text-xs">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Shortcut</th>
                    <th className="px-5 py-3 font-semibold">Message</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Assistant</th>
                    <th className="px-5 py-3 font-semibold">Updated</th>
                    <th className="px-5 py-3 font-semibold">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {state.visible.map((record) => (
                    <ResponseRow
                      key={record.id}
                      record={record}
                      scope={state.scope}
                      records={records}
                      pending={state.pendingIds.includes(record.id)}
                      error={state.rowErrors[record.id]}
                      onToggle={state.toggle}
                      onEdit={state.openEdit}
                      onDelete={state.setDeleteTarget}
                    />
                  ))}
                </tbody>
              </table>
            </CannedScrollPane>
            <CannedScrollPane
              className="divide-line flex min-h-0 flex-1 flex-col divide-y overflow-y-auto overscroll-none md:hidden"
              hasMore={state.hasMore}
              loadedCount={state.visible.length}
              onLoadMore={state.loadMore}
            >
              {state.visible.map((record) => (
                <ResponseCard
                  key={record.id}
                  record={record}
                  scope={state.scope}
                  records={records}
                  pending={state.pendingIds.includes(record.id)}
                  error={state.rowErrors[record.id]}
                  onToggle={state.toggle}
                  onEdit={state.openEdit}
                  onDelete={state.setDeleteTarget}
                />
              ))}
            </CannedScrollPane>
          </section>
        )}
      </main>
      <p className="sr-only" aria-live="polite">
        {state.announcement}
      </p>
      <ResponseForm
        form={state.form}
        records={records}
        sites={state.sites}
        formError={state.formError}
        submitting={state.submitting}
        onChange={state.setForm}
        onSubmit={state.saveForm}
        onRequestClose={state.requestClose}
        shortcutRef={state.shortcutRef}
      />
      <AlertDialog open={state.discardOpen} onOpenChange={state.setDiscardOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard changes?</AlertDialogTitle>
            <AlertDialogDescription>
              Your unsaved response changes will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogClose render={<Button variant="outline">Keep editing</Button>} />
            <Button
              variant="default"
              onClick={() => {
                state.setDiscardOpen(false)
                state.setForm(null)
              }}
            >
              Discard changes
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <DeleteDialog
        target={state.deleteTarget}
        sites={state.sites}
        deleting={state.deleting}
        onCancel={() => state.setDeleteTarget(null)}
        onConfirm={() => void state.deleteResponse()}
      />
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        sites={state.sites}
        onImported={async () => {
          await state.load()
        }}
      />
      {historyOpen ? (
        <ImportHistoryDialog
          sites={state.sites}
          onClose={() => setHistoryOpen(false)}
          onViewCurrent={(id) => {
            const record = records.find((item) => item.id === id)
            if (record) {
              setHistoryOpen(false)
              state.openEdit(record)
            }
          }}
        />
      ) : null}
    </div>
  )
}
