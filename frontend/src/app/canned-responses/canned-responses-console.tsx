"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-function-as-prop -- StaffHeader actions and dialog callbacks use the current library state. */

import { Plus, Search } from "lucide-react"

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
import { Input } from "@/components/ui/input"

import { DeleteDialog, ResponseForm } from "./canned-response-dialogs"
import {
  CannedResponsesSkeleton,
  EmptyState,
  Pagination,
  ResponseCard,
  ResponseRow,
} from "./canned-response-list"
import { CannedResponseSelect, scopeOptions, statusOptions } from "./canned-response-select"
import { useCannedResponsesState } from "./use-canned-responses-state"

// oxlint-disable-next-line eslint/max-lines-per-function -- Compose the library controls, list, and edit dialogs.
export const CannedResponsesConsole = () => {
  const state = useCannedResponsesState()

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
            <Button className="bg-ember hover:bg-ember/90 mt-5" onClick={() => void state.load()}>
              Retry
            </Button>
          </div>
        </main>
      </div>
    )
  }

  if (state.records === null) {
    return (
      <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
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
    <div className="view-transition-enter bg-ice min-h-0 min-w-0 flex-1 overflow-y-auto">
      <StaffHeader
        title="Canned responses"
        description="Reuse approved specialist wording across chats."
        action={
          <Button className="bg-ember hover:bg-ember/90" onClick={state.openCreate}>
            <Plus aria-hidden="true" /> Add response
          </Button>
        }
      />
      <main
        id="main-content"
        className="flex w-full min-w-0 flex-col gap-4 px-5 py-6 lg:px-8 lg:py-8"
      >
        <section className="border-line bg-paper rounded-xl border p-4 sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[minmax(15rem,0.8fr)_minmax(18rem,1.2fr)_10rem]">
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
              <span>Search</span>
              <span className="border-line bg-ice flex h-10 items-center gap-2 rounded-[8px] border px-3">
                <Search aria-hidden="true" className="text-mute size-4" />
                <Input
                  aria-label="Search canned responses"
                  value={state.query}
                  onChange={(event) => state.updateQuery(event.target.value)}
                  placeholder="# or message…"
                  className="h-auto border-0 bg-transparent p-0 shadow-none focus-visible:ring-0"
                />
              </span>
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
          <EmptyState scope={state.scope} sites={state.sites} onAdd={state.openCreate} />
        ) : (
          <section className="border-line bg-paper overflow-hidden rounded-xl border">
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                <thead className="bg-ice-2 text-ink text-xs">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Shortcut</th>
                    <th className="px-5 py-3 font-semibold">Message</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
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
            </div>
            <div className="divide-line flex flex-col divide-y md:hidden">
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
            </div>
          </section>
        )}
        {state.totalPages > 1 ? (
          <Pagination
            page={state.page}
            total={state.totalPages}
            onChange={(next) => {
              state.setPage(next)
              state.updateUrl({ page: next })
            }}
          />
        ) : null}
      </main>
      <p className="sr-only" aria-live="polite">
        {state.announcement}
      </p>
      <ResponseForm
        form={state.form}
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
              className="bg-ember hover:bg-ember/90"
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
    </div>
  )
}
