import { Pencil } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Row controls close over response records. */
import { RetryError } from "@/components/admin/retry-error"
import { type SiteRecord } from "@/components/admin/staff-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { StateIcon } from "@/components/ui/state-icon"
import { Switch } from "@/components/ui/switch"

import {
  botState,
  followsLabel,
  formatDate,
  scopeLabel,
  statusClass,
  type BotState,
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
    <td className="text-steel px-5 py-3 font-mono text-sm font-bold">
      <span>#{record.shortcut}</span>
      {(record.aliases ?? []).length > 0 ? (
        <span className="text-mute mt-1 block text-xs font-normal">
          {(record.aliases ?? []).map((alias) => `#${alias}`).join(" ")}
        </span>
      ) : null}
    </td>
    <td className="max-w-md px-5 py-3">
      <p className="text-ink line-clamp-2">{record.body}</p>
      {overrideNote(record, scope, records)}
      <RowMeta record={record} records={records} />
    </td>
    <td className="px-5 py-3">
      <ResponseToggle record={record} pending={pending} onToggle={onToggle} />
      {error ? <RetryError text={error} onRetry={() => void onToggle(record)} /> : null}
    </td>
    <td className="px-5 py-3">
      <BotPill record={record} />
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
          <StateIcon name="trash" />
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
        {(record.aliases ?? []).length > 0 ? (
          <p className="text-mute mt-1 font-mono text-xs">
            {(record.aliases ?? []).map((alias) => `#${alias}`).join(" ")}
          </p>
        ) : null}
        <p className="text-ink mt-2 line-clamp-3 text-sm leading-6">{record.body}</p>
        {overrideNote(record, scope, records)}
        <RowMeta record={record} records={records} />
        <div className="mt-2">
          <BotPill record={record} />
        </div>
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

const BOT_PILL: Record<BotState, { label: string; className: string }> = {
  available: {
    label: "Assistant",
    className: "bg-[#E8F5EE] text-[#247A4D] dark:bg-[#163627] dark:text-[#8DDEAE]",
  },
  staff: {
    label: "Staff only",
    className: "bg-ice-2 text-mute dark:bg-white/10 dark:text-white/60",
  },
  blocked: { label: "Blocked", className: "bg-[#FCEBDD] text-ember dark:bg-[#3A2415]" },
}

export const BotPill = ({ record }: { record: CannedReplyRecord }) => {
  const state = botState(record)
  return (
    <div>
      <Badge className={BOT_PILL[state].className}>{BOT_PILL[state].label}</Badge>
      {state === "blocked" ? (
        <span className="text-mute mt-1 block max-w-52 text-xs">{record.bot_block_reason}</span>
      ) : null}
    </div>
  )
}

const RowMeta = ({
  record,
  records,
}: {
  record: CannedReplyRecord
  records: CannedReplyRecord[]
}) => {
  const follows = followsLabel(record, records)
  if (!follows && !record.hands_off) return null
  return (
    <p className="text-mute mt-1 flex flex-wrap gap-x-3 text-xs">
      {follows ? <span>{follows}</span> : null}
      {record.hands_off ? <span>Connects a specialist</span> : null}
    </p>
  )
}

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

export const CannedScrollPane = ({
  className,
  hasMore,
  loadedCount,
  onLoadMore,
  children,
}: {
  className: string
  hasMore: boolean
  loadedCount: number
  onLoadMore: () => void
  children: ReactNode
}) => {
  const scrollRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = scrollRef.current
    const trigger = triggerRef.current
    if (!root || !trigger || !hasMore || typeof IntersectionObserver === "undefined") {
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          onLoadMore()
        }
      },
      { root, rootMargin: "0px 0px 240px" },
    )
    observer.observe(trigger)
    return () => observer.disconnect()
    // Re-attach after each batch so a sentinel still in view can reveal the next window.
    // oxlint-disable-next-line react/exhaustive-effect-dependencies
  }, [hasMore, loadedCount, onLoadMore])

  return (
    <div ref={scrollRef} className={className}>
      {children}
      {hasMore ? (
        <div
          ref={triggerRef}
          aria-live="polite"
          className="flex min-h-12 items-center justify-center px-4 py-3"
        >
          <span className="text-mute text-xs">Scroll for more responses</span>
        </div>
      ) : null}
    </div>
  )
}

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
