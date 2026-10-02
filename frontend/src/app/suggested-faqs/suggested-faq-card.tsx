"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Card actions close over this question. */

import { RetryError } from "@/components/admin/retry-error"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import {
  chatCount,
  formatDay,
  handledLabel,
  type GapQueue,
  type GapRecord,
  type GapView,
} from "./suggested-faq-model"
import { GapNote } from "./suggested-faq-note"

type CardProps = {
  gap: GapRecord
  view: GapView
  queue: GapQueue
  websiteName: string | null
  pending: boolean
  error: string
  onAnswer: (gap: GapRecord) => void
  onDismiss: (gap: GapRecord) => void
  onReopen: (gap: GapRecord) => void
  onSaveNote: (gap: GapRecord, note: string) => Promise<boolean>
}

const CountBox = ({ count }: { count: number }) => (
  <div
    aria-hidden="true"
    className="bg-ice-2 text-navy flex size-14 shrink-0 flex-col items-center justify-center rounded-[8px]"
  >
    <span className="font-mono text-lg leading-none font-bold">{count}</span>
    <span className="text-mute mt-1 text-[10px] font-semibold tracking-[0.08em] uppercase">
      {count === 1 ? "chat" : "chats"}
    </span>
  </div>
)

const Meta = ({
  gap,
  view,
  queue,
  websiteName,
}: Pick<CardProps, "gap" | "view" | "queue" | "websiteName">) => (
  <p className="text-mute mt-1 flex flex-wrap gap-x-2 text-xs">
    <span>
      {view === "open"
        ? `Asked in ${chatCount(gap.conversations)} in the last ${queue.window_days} days`
        : `Asked in ${chatCount(gap.conversations)}`}
    </span>
    <span>Last asked {formatDay(gap.last_seen_at)}</span>
    {gap.resolved_at ? <span>Handled {formatDay(gap.resolved_at)}</span> : null}
    {websiteName ? <span>{websiteName}</span> : null}
  </p>
)

const Actions = ({
  gap,
  view,
  pending,
  onAnswer,
  onDismiss,
  onReopen,
}: Pick<CardProps, "gap" | "view" | "pending" | "onAnswer" | "onDismiss" | "onReopen">) => {
  if (view !== "open") {
    return (
      <Button
        type="button"
        variant="outline"
        size="lg"
        disabled={pending}
        aria-label={`Reopen: ${gap.question}`}
        onClick={() => onReopen(gap)}
      >
        Reopen
      </Button>
    )
  }
  return (
    <>
      <Button
        type="button"
        variant="default"
        size="lg"
        className="font-bold"
        aria-label={`Answer: ${gap.question}`}
        onClick={() => onAnswer(gap)}
      >
        Answer
      </Button>
      <Button
        type="button"
        variant="outline"
        size="lg"
        disabled={pending}
        aria-label={`Dismiss: ${gap.question}`}
        onClick={() => onDismiss(gap)}
      >
        Dismiss
      </Button>
    </>
  )
}

export const SuggestedFaqCard = (props: CardProps) => {
  const { gap, view, queue, error } = props
  return (
    <article
      aria-labelledby={`faq-${gap.id}`}
      className="border-line bg-paper rounded-xl border p-5 transition-[opacity] duration-150"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <CountBox count={gap.conversations} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id={`faq-${gap.id}`} className="text-navy heading text-base">
              {gap.question}
            </h2>
            {gap.spiking ? (
              <Badge
                className="bg-ember/10 text-ember"
                title={`${queue.spike_conversations} or more different chats in the last ${queue.spike_hours} hours`}
              >
                Spiking
              </Badge>
            ) : null}
            {view === "open" ? null : (
              <Badge className="bg-ice-2 text-steel">{handledLabel(gap.status)}</Badge>
            )}
          </div>
          <Meta gap={gap} view={view} queue={queue} websiteName={props.websiteName} />
          {gap.examples.length > 0 ? (
            <div className="mt-3">
              <p className="text-ink text-xs font-semibold">Also asked as</p>
              <ul className="text-mute mt-1 flex flex-col gap-0.5 text-sm">
                {gap.examples.map((example) => (
                  <li key={example}>{example}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <GapNote gap={gap} onSave={props.onSaveNote} />
        </div>
        <div className="flex shrink-0 gap-2">
          <Actions {...props} />
        </div>
      </div>
      {error ? (
        <RetryError
          text={error}
          onRetry={() => (view === "open" ? props.onDismiss(gap) : props.onReopen(gap))}
          className="mt-3"
        />
      ) : null}
    </article>
  )
}
