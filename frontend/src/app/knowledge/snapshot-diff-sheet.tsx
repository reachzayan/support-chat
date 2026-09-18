"use client"

import { useCallback } from "react"

import type { KbDiff, KbEvidenceUnit, KbProgressRecord } from "@/components/admin/staff-api"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"

import { describeProgressEvent } from "./knowledge-format"

type SnapshotDiffSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  diff: KbDiff | null
  status: string
  canRollback: boolean
  rollbackBusy: boolean
  onRollback: () => void
  progress: KbProgressRecord | null
}

export const SnapshotDiffSheet = ({
  open,
  onOpenChange,
  diff,
  status,
  canRollback,
  rollbackBusy,
  onRollback,
  progress,
}: SnapshotDiffSheetProps) => {
  const handleOpenChange = useCallback(
    (next: boolean) => {
      onOpenChange(next)
    },
    [onOpenChange],
  )
  const handleRollback = useCallback(() => {
    onRollback()
  }, [onRollback])
  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        className="bg-paper border-line w-full gap-0 overflow-y-auto p-0 data-[side=right]:sm:max-w-2xl"
      >
        <SheetHeader className="border-line border-b px-5 py-4">
          <SheetTitle>Source progress</SheetTitle>
          <SheetDescription className="text-mute text-xs">
            Processing history and evidence changes for this source.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-5 px-5 py-5">
          <CrawlActivity progress={progress} />
          <p aria-live="polite" className="text-mute text-xs">
            {status}
          </p>
          {diff === null ? (
            <p className="text-ink text-sm">Loading changes.</p>
          ) : (
            <>
              <DiffSection title="Added" units={diff.added} empty="No added units." />
              <ChangedSection items={diff.changed} />
              <DiffSection title="Removed" units={diff.removed} empty="No removed units." />
            </>
          )}
        </div>
        {canRollback ? (
          <SheetFooter className="border-line border-t">
            <button
              type="button"
              onClick={handleRollback}
              disabled={rollbackBusy}
              className="bg-ember hover:bg-ember-mid focus-visible:ring-steel dark:text-navy-deep rounded-[8px] px-4 py-2.5 text-sm font-bold text-white focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              Roll back to previous snapshot
            </button>
          </SheetFooter>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

const CrawlActivity = ({ progress }: { progress: KbProgressRecord | null }) => {
  if (!progress || (progress.current_jobs.length === 0 && progress.recent_events.length === 0)) {
    return null
  }
  return (
    <section className="border-line bg-paper rounded-xl border px-5 py-5" aria-live="polite">
      <p className="text-mute text-[11px] font-semibold tracking-[0.2em] uppercase">
        Processing history
      </p>
      <h2 className="text-navy heading mt-1 text-base">Latest runs</h2>
      {progress.current_jobs.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {progress.current_jobs.map((job) => (
            <li key={`${job.page_url}:${job.started_at}`} className="flex flex-col gap-0.5 text-xs">
              <span className="text-mute min-w-0 truncate font-mono">{job.page_url}</span>
              <span className="text-ink">
                {job.message ??
                  describeProgressEvent({ stage: job.stage, state: "running", error_code: null })}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      <ul className="border-line mt-3 divide-y border-t">
        {progress.recent_events.slice(0, 10).map((event) => {
          const summary = describeProgressEvent(event)
          return (
            <li
              key={`${event.page_url}:${event.timestamp}`}
              className="flex flex-col gap-0.5 py-2 text-xs"
            >
              <span className="text-mute min-w-0 truncate font-mono">{event.page_url}</span>
              <span className={event.error_code ? "text-ember font-semibold" : "text-ink"}>
                {summary}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

const DiffSection = ({
  title,
  units,
  empty,
}: {
  title: string
  units: KbEvidenceUnit[]
  empty: string
}) => {
  return (
    <section>
      <h3 className="text-navy heading text-sm">{title}</h3>
      {units.length === 0 ? (
        <p className="text-mute mt-2 text-xs">{empty}</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {units.map((unit) => (
            <li
              key={`${unit.kind}-${unit.heading}-${unit.answer_verbatim}`}
              className="border-line rounded-[8px] border px-4 py-3"
            >
              <p className="text-navy heading text-sm">{unit.canonical_question ?? unit.heading}</p>
              <pre className="text-ink mt-2 font-sans text-sm leading-6 whitespace-pre-wrap">
                {unit.answer_verbatim}
              </pre>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

const ChangedSection = ({
  items,
}: {
  items: { before: KbEvidenceUnit; after: KbEvidenceUnit }[]
}) => {
  return (
    <section>
      <h3 className="text-navy heading text-sm">Changed</h3>
      {items.length === 0 ? (
        <p className="text-mute mt-2 text-xs">No changed units.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {items.map((item) => (
            <li
              key={`${item.before.heading}-${item.after.heading}`}
              className="border-line rounded-[8px] border px-4 py-3"
            >
              <p className="text-navy heading text-sm">
                {item.after.canonical_question ?? item.after.heading}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <pre className="bg-ice text-ink rounded-[8px] p-3 font-sans text-xs leading-5 whitespace-pre-wrap">
                  {item.before.answer_verbatim}
                </pre>
                <pre className="bg-ice-2 text-ink rounded-[8px] p-3 font-sans text-xs leading-5 whitespace-pre-wrap">
                  {item.after.answer_verbatim}
                </pre>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
