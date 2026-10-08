"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-new-array-as-prop, react-perf/jsx-no-jsx-as-prop -- Website options and card actions use the current queue. */

import { CannedResponseSelect } from "@/app/canned-responses/canned-response-select"
import { useOptionalAdminUser } from "@/components/admin/admin-shell"
import { StaffHeader } from "@/components/admin/staff-nav"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

import { AnswerDialog } from "./suggested-faq-answer-dialog"
import { SuggestedFaqCard } from "./suggested-faq-card"
import { SuggestedFaqInfo } from "./suggested-faq-info"
import type { GapQueue, GapView } from "./suggested-faq-model"
import { ViewTabs } from "./suggested-faq-tabs"
import { ALL_WEBSITES, useSuggestedFaqsState } from "./use-suggested-faqs-state"

const TITLE = "Suggested FAQs"
const DESCRIPTION = "Questions visitors keep asking that the assistant could not answer."

const PageFrame = ({ children, queue }: { children: React.ReactNode; queue: GapQueue | null }) => (
  <div className="view-transition-enter bg-ice flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
    <StaffHeader
      title={TITLE}
      description={DESCRIPTION}
      titleAction={<SuggestedFaqInfo queue={queue} />}
    />
    {children}
  </div>
)

const viewHelp = (view: GapView, queue: GapQueue) => {
  if (view === "answered") {
    return "Questions you answered. Reopen one if the answer did not stop the misses."
  }
  if (view === "dismissed") {
    return "Questions you dismissed. Reopen one to put it back in the queue."
  }
  return `Shown after a question stumps the assistant in ${queue.min_conversations} different chats within ${queue.window_days} days, or ${queue.spike_conversations} within ${queue.spike_hours} hours. Nothing here changes what visitors see until you save an answer.`
}

const EmptyQueue = ({ view, queue }: { view: GapView; queue: GapQueue }) => {
  if (view !== "open") {
    return (
      <section className="border-line bg-paper rounded-xl border p-8 text-center">
        <p className="text-navy heading text-base">
          {view === "answered" ? "Nothing answered yet" : "Nothing dismissed"}
        </p>
      </section>
    )
  }
  return (
    <section className="border-line bg-paper rounded-xl border p-8 text-center">
      <p className="text-navy heading text-base">No repeated questions yet</p>
      <p className="text-mute mx-auto mt-2 max-w-md text-sm">
        A question appears here after the assistant could not answer it in {queue.min_conversations}{" "}
        different chats within {queue.window_days} days.
      </p>
    </section>
  )
}

// oxlint-disable-next-line eslint/max-lines-per-function -- The route composes the tabs, filter, queue, and answer dialog from one state hook.
export const SuggestedFaqsConsole = () => {
  const state = useSuggestedFaqsState()
  const staff = useOptionalAdminUser()
  const { queue } = state

  if (state.loadError) {
    return (
      <PageFrame queue={queue}>
        <main id="main-content" className="flex flex-1 items-center justify-center p-6">
          <div className="border-line bg-paper w-full max-w-md rounded-xl border p-6 text-center">
            <p className="text-navy heading text-base">Suggested FAQs could not be loaded</p>
            <p className="text-mute mt-2 text-sm">Check your connection and try again.</p>
            <Button
              variant="default"
              size="lg"
              className="mt-5 font-bold"
              onClick={() => void state.reload()}
            >
              Retry
            </Button>
          </div>
        </main>
      </PageFrame>
    )
  }

  if (!state.hasLoaded) {
    return (
      <PageFrame queue={queue}>
        <main className="flex flex-col gap-4 px-4 py-4 sm:px-5 sm:py-6 lg:px-8 lg:py-8">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </main>
      </PageFrame>
    )
  }

  const websiteName = (siteId: string) =>
    state.sites.length > 1 ? (state.sites.find((site) => site.id === siteId)?.name ?? null) : null

  return (
    <PageFrame queue={queue}>
      <main
        id="main-content"
        className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-none px-4 py-4 sm:px-5 sm:py-6 lg:px-8 lg:py-8"
      >
        <ViewTabs view={state.view} onSelect={state.selectView} />
        <section className="border-line bg-paper shrink-0 rounded-xl border p-4 sm:p-5">
          <div className="text-ink flex max-w-xs flex-col gap-1.5 text-xs font-medium">
            <span>Website</span>
            <CannedResponseSelect
              value={state.website}
              onValueChange={state.selectWebsite}
              items={[
                { value: ALL_WEBSITES, label: "All websites" },
                ...state.sites.map((site) => ({ value: site.id, label: site.name })),
              ]}
              label="Website"
            />
          </div>
          {queue ? <p className="text-mute mt-4 text-xs">{viewHelp(state.view, queue)}</p> : null}
        </section>
        <div role="tabpanel" aria-label={state.view} className="flex flex-col gap-3">
          {queue === null ? (
            <Skeleton className="h-32 w-full rounded-xl" />
          ) : queue.items.length === 0 ? (
            <EmptyQueue view={state.view} queue={queue} />
          ) : (
            queue.items.map((gap) => (
              <SuggestedFaqCard
                key={gap.id}
                gap={gap}
                view={state.view}
                queue={queue}
                websiteName={websiteName(gap.site_id)}
                pending={state.pendingId === gap.id}
                error={state.cardErrors[gap.id] ?? ""}
                onAnswer={state.openAnswer}
                onDismiss={state.dismiss}
                onReopen={state.reopen}
                onSaveNote={state.saveNote}
              />
            ))
          )}
        </div>
      </main>
      <p className="sr-only" aria-live="polite">
        {state.announcement}
      </p>
      <AnswerDialog
        gap={state.answering}
        isAdmin={staff?.is_admin === true}
        replies={state.replies}
        similar={state.similar}
        submitting={state.submitting}
        error={state.saveError}
        onClose={state.closeAnswer}
        onSubmit={state.submitAnswer}
      />
    </PageFrame>
  )
}
