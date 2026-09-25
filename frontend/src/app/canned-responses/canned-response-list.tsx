import { Pencil, Trash2 } from "lucide-react"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Row controls close over response records. */
import { RetryError } from "@/components/admin/retry-error"
import { type SiteRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"

import {
  formatDate,
  scopeLabel,
  statusClass,
  type CannedReplyRecord,
  type Scope,
} from "./canned-response-model"

export const ResponseRow = ({
  record,
  scope,
  records,
  pending,
  error,
  onToggle,
  onEdit,
  onDelete,
}: ResponseItemProps) => (
  <tr className="border-line hover:bg-ice/60 border-t transition-[opacity,transform,background-color] duration-150">
    <td className="text-steel px-5 py-3 font-mono text-sm font-bold">#{record.shortcut}</td>
    <td className="max-w-md px-5 py-3">
      <p className="text-ink line-clamp-2">{record.body}</p>
      {overrideNote(record, scope, records)}
    </td>
    <td className="px-5 py-3">
      <ResponseToggle record={record} pending={pending} onToggle={onToggle} />
      {error ? <RetryError text={error} onRetry={() => void onToggle(record)} /> : null}
    </td>
    <td className="text-mute px-5 py-3 text-xs">{formatDate(record.updated_at)}</td>
    <td className="px-5 py-3">
      <div className="flex justify-end gap-1">
        <Button variant="ghost" size="sm" onClick={() => onEdit(record)}>
          <Pencil aria-hidden="true" /> Edit
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Remove #${record.shortcut}`}
          onClick={() => onDelete(record)}
        >
          <Trash2 aria-hidden="true" />
        </Button>
      </div>
    </td>
  </tr>
)

type ResponseItemProps = {
  record: CannedReplyRecord
  scope: Scope
  records: CannedReplyRecord[]
  pending: boolean
  error?: string
  onToggle: (record: CannedReplyRecord) => Promise<void>
  onEdit: (record: CannedReplyRecord) => void
  onDelete: (record: CannedReplyRecord) => void
}

export const ResponseCard = ({
  record,
  scope,
  records,
  pending,
  error,
  onToggle,
  onEdit,
  onDelete,
}: ResponseItemProps) => (
  <article className="p-4 transition-[opacity,transform] duration-150">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-steel font-mono text-sm font-bold">#{record.shortcut}</p>
        <p className="text-ink mt-2 line-clamp-3 text-sm leading-6">{record.body}</p>
        {overrideNote(record, scope, records)}
      </div>
      <ResponseToggle record={record} pending={pending} onToggle={onToggle} stacked />
    </div>
    <div className="mt-4 flex items-center justify-between">
      <span className="text-mute text-xs">Updated {formatDate(record.updated_at)}</span>
      <div className="flex gap-1">
        <Button variant="ghost" size="sm" onClick={() => onEdit(record)}>
          Edit
        </Button>
        <Button variant="ghost" size="sm" className="text-ember" onClick={() => onDelete(record)}>
          Remove
        </Button>
      </div>
    </div>
    {error ? <RetryError text={error} onRetry={() => void onToggle(record)} /> : null}
  </article>
)

const overrideNote = (record: CannedReplyRecord, scope: Scope, records: CannedReplyRecord[]) =>
  scope !== "general" &&
  !record.enabled &&
  records.some((row) => row.site_id === null && row.shortcut === record.shortcut) ? (
    <p className="text-mute mt-1 text-xs">
      Disabled here. The General #{record.shortcut} response also remains hidden.
    </p>
  ) : null

export const EmptyState = ({
  scope,
  sites,
  onAdd,
}: {
  scope: Scope
  sites: SiteRecord[]
  onAdd: () => void
}) => (
  <section className="border-line bg-paper rounded-xl border p-8 text-center">
    <p className="text-navy heading text-base">
      {scope === "general" ? "No General responses yet" : "No website responses yet"}
    </p>
    <p className="text-mute mx-auto mt-2 max-w-md text-sm">
      {scope === "general"
        ? "Responses created here work across every website."
        : `General responses remain available unless this website defines the same shortcut. ${scopeLabel(scope, sites)} can have its own approved wording.`}
    </p>
    <Button variant="default" size="lg" className="mt-5 font-bold" onClick={onAdd}>
      Add {scope === "general" ? "general" : "website"} response
    </Button>
  </section>
)

export const Pagination = ({
  page,
  total,
  onChange,
}: {
  page: number
  total: number
  onChange: (page: number) => void
}) => (
  <div className="flex items-center justify-end gap-3">
    <span className="text-mute text-xs">
      Page {page} of {total}
    </span>
    <Button variant="outline" disabled={page === 1} onClick={() => onChange(page - 1)}>
      Previous
    </Button>
    <Button variant="outline" disabled={page === total} onClick={() => onChange(page + 1)}>
      Next
    </Button>
  </div>
)

export const CannedResponsesSkeleton = () => (
  <main className="flex flex-col gap-4 px-5 py-6 lg:px-8 lg:py-8">
    <Skeleton className="h-28 w-full rounded-xl" />
    <Skeleton className="h-56 w-full rounded-xl" />
  </main>
)

const ResponseToggle = ({
  record,
  pending,
  onToggle,
  stacked = false,
}: Pick<ResponseItemProps, "record" | "pending" | "onToggle"> & { stacked?: boolean }) => (
  <div className={`flex gap-2 ${stacked ? "flex-col items-end" : "items-center"}`}>
    <Switch
      aria-label={`${record.enabled ? "Disable" : "Enable"} #${record.shortcut}`}
      checked={record.enabled}
      disabled={pending}
      onCheckedChange={() => void onToggle(record)}
    />
    <Badge className={statusClass(record.enabled)}>{record.enabled ? "Enabled" : "Disabled"}</Badge>
  </div>
)
