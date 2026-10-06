"use client"
/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- History actions use the selected batch and pagination offset. */

import { Download } from "lucide-react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import {
  useCannedImportHistory,
  type ImportBatch,
  type ImportEntry,
} from "./use-canned-import-history"

const date = (value: string) =>
  new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  )
const ACTIONS: Record<string, string> = {
  create: "Created",
  update: "Updated",
  unchanged: "Already in the library",
  skip: "Skipped",
}

const UploadMetadata = ({ batch }: { batch: ImportBatch }) => (
  <div className="text-mute space-y-1 text-xs">
    <p>
      <time dateTime={batch.uploaded_at}>{date(batch.uploaded_at)}</time> ·{" "}
      <span>{batch.uploaded_by_name ?? "Unknown uploader"}</span>
    </p>
    <p>
      {batch.created} created · {batch.updated} updated · {batch.skipped} skipped or unchanged
    </p>
  </div>
)

const entryScope = (entry: ImportEntry, sites: SiteRecord[]) => {
  if (entry.action === "skip") return "Not imported"
  if (entry.snapshot.site_id === null) return "General — all websites"
  return (
    sites.find((site) => site.id === entry.snapshot.site_id)?.name ?? "Website no longer available"
  )
}

const SnapshotRow = ({
  entry,
  sites,
  onViewCurrent,
}: {
  entry: ImportEntry
  sites: SiteRecord[]
  onViewCurrent: (id: string) => void
}) => {
  const scope = entryScope(entry, sites)
  return (
    <li className="border-line border-b py-4 last:border-b-0">
      <div className="text-navy flex flex-wrap justify-between gap-2 text-sm font-bold">
        <span>
          {entry.snapshot.shortcut ? `#${entry.snapshot.shortcut}` : `Entry ${entry.row_number}`}
        </span>
        <span className="text-mute text-xs font-medium">
          {ACTIONS[entry.action] ?? entry.action}
        </span>
      </div>
      <p className="text-mute mt-1 text-xs">
        {scope}
        {entry.snapshot.livechat_id != null ? ` · LiveChat ID ${entry.snapshot.livechat_id}` : ""}
      </p>
      {entry.snapshot.body ? (
        <p className="text-ink mt-3 text-sm leading-6 break-words whitespace-pre-wrap">
          {entry.snapshot.body}
        </p>
      ) : null}
      {entry.snapshot.reason ? (
        <p className="text-mute mt-2 text-xs">{entry.snapshot.reason}</p>
      ) : null}
      {entry.snapshot.disable_reason ? (
        <p className="text-mute mt-2 text-xs">{entry.snapshot.disable_reason}</p>
      ) : null}
      {entry.reply_id ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onViewCurrent(entry.reply_id!)}
          className="text-steel mt-2"
        >
          View current response
        </Button>
      ) : null}
    </li>
  )
}

const UploadList = ({ history }: { history: ReturnType<typeof useCannedImportHistory> }) => (
  <>
    {history.batches.length === 0 && !history.busy && !history.error ? (
      <p className="text-mute py-8 text-center text-sm">
        No CSV uploads recorded yet. Completed imports will appear here.
      </p>
    ) : null}
    <ul className="divide-line divide-y">
      {history.batches.map((batch) => (
        <li key={batch.id} className="py-4">
          <Button
            type="button"
            variant="ghost"
            className="text-navy mb-2 h-auto max-w-full justify-start px-0 text-left break-words whitespace-normal"
            aria-label={`View upload ${batch.id}: ${batch.filename}`}
            onClick={() => void history.view(batch.id)}
            disabled={history.busy}
          >
            Upload {batch.id} · {batch.filename}
          </Button>
          <UploadMetadata batch={batch} />
        </li>
      ))}
    </ul>
    {history.hasMore ? (
      <Button
        type="button"
        variant="outline"
        disabled={history.busy}
        onClick={() => void history.load(history.batches.length)}
      >
        Load older uploads
      </Button>
    ) : null}
  </>
)

const UploadDetail = ({
  history,
  detail,
  sites,
  onViewCurrent,
}: {
  history: ReturnType<typeof useCannedImportHistory>
  detail: NonNullable<ReturnType<typeof useCannedImportHistory>["detail"]>
  sites: SiteRecord[]
  onViewCurrent: (id: string) => void
}) => (
  <>
    <h2 className="text-navy text-base font-bold break-words">
      Upload {detail.batch.id} · {detail.batch.filename}
    </h2>
    <UploadMetadata batch={detail.batch} />
    <Button
      type="button"
      variant="outline"
      className="w-fit"
      disabled={history.busy}
      onClick={() => void history.download(detail.batch)}
    >
      <Download aria-hidden="true" data-icon="inline-start" />
      Download original CSV
    </Button>
    <p className="text-mute text-xs">
      These are saved copies from this upload. Later edits to the library do not change them.
    </p>
    <ul>
      {detail.rows.map((entry) => (
        <SnapshotRow
          key={entry.row_number}
          entry={entry}
          sites={sites}
          onViewCurrent={onViewCurrent}
        />
      ))}
    </ul>
    {detail.has_more ? (
      <Button
        type="button"
        variant="outline"
        disabled={history.busy}
        onClick={() => void history.view(detail.batch.id, detail.rows.length)}
      >
        Load more responses
      </Button>
    ) : null}
  </>
)

export const ImportHistoryDialog = ({
  sites,
  onClose,
  onViewCurrent,
}: {
  sites: SiteRecord[]
  onClose: () => void
  onViewCurrent: (id: string) => void
}) => {
  const history = useCannedImportHistory()
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>CSV upload history</DialogTitle>
          <DialogDescription>
            Completed imports, with the original file and the wording saved at that time. Earlier
            uploads cannot be reconstructed.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-col gap-3 overflow-y-auto px-5 py-4">
          {history.selected !== null ? (
            <Button type="button" variant="ghost" className="w-fit" onClick={history.back}>
              Back to uploads
            </Button>
          ) : null}
          {history.error ? (
            <div role="alert" className="text-ember text-sm">
              {history.error}
              <Button
                type="button"
                variant="outline"
                className="ml-2"
                onClick={() =>
                  void (history.selected === null ? history.load() : history.view(history.selected))
                }
              >
                Retry
              </Button>
            </div>
          ) : null}
          {history.busy ? <output className="text-mute text-sm">Loading…</output> : null}
          {history.selected === null ? (
            <UploadList history={history} />
          ) : history.detail ? (
            <UploadDetail
              history={history}
              detail={history.detail}
              sites={sites}
              onViewCurrent={onViewCurrent}
            />
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
