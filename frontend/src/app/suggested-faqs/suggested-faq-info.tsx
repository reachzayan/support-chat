"use client"

import { useCallback, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { StateIcon } from "@/components/ui/state-icon"

import type { GapQueue } from "./suggested-faq-model"

const Explanation = ({ queue }: { queue: GapQueue | null }) => (
  <div className="text-ink flex min-h-0 flex-col gap-5 overflow-y-auto px-5 py-4 text-sm leading-6">
    <section>
      <h2 className="text-navy font-bold">Where the questions come from</h2>
      <p>
        When the assistant cannot find a verified answer in a website’s knowledge or canned
        responses, the question can be recorded here. Similar phrasings are grouped together for
        that website. Service outages and questions the assistant answered are excluded.
      </p>
    </section>
    <section>
      <h2 className="text-navy font-bold">When a question appears</h2>
      <p>
        A question reaches Open after it goes unanswered in {queue?.min_conversations ?? 5}{" "}
        different chats within {queue?.window_days ?? 14} days, or {queue?.spike_conversations ?? 3}{" "}
        different chats within {queue?.spike_hours ?? 24} hours. Repeating it in one chat does not
        increase the chat count. “Spiking” marks the faster increase.
      </p>
      <p className="mt-2">
        Use Website to filter the list. Each card shows the number of chats, when the question was
        last seen, and examples of how visitors phrased it. Counts in Open cover the current time
        window.
      </p>
    </section>
    <section>
      <h2 className="text-navy font-bold">How to answer one</h2>
      <p>
        Open Answer, review the examples and any available specialist replies or similar existing
        content, then check the wording before saving.
      </p>
      <ul className="mt-2 list-disc space-y-2 pl-5">
        <li>
          <strong>Quick reply:</strong> saves a canned response for that website. Specialists can
          insert it with a #shortcut, and the assistant can use its approved wording when it matches
          a future question.
        </li>
        <li>
          <strong>Knowledge text:</strong> adds reference material for that website. Only admins can
          add it. The assistant can answer from it after processing finishes; check its status in
          Knowledge.
        </li>
      </ul>
      <p className="mt-2">
        A suggestion alone does not change the assistant’s answers. Saving an answer adds material
        for future chats; it does not send a reply to earlier visitors.
      </p>
    </section>
    <section>
      <h2 className="text-navy font-bold">Open, Answered, and Dismissed</h2>
      <p>
        <strong>Open</strong> needs review. <strong>Answered</strong> contains questions you saved
        as a quick reply or knowledge text. <strong>Dismissed</strong> contains suggestions you
        chose not to answer, such as irrelevant questions.
      </p>
      <p className="mt-2">
        Reopen an answered or dismissed suggestion to review it again. Reopening does not remove its
        saved response or knowledge. Notes are internal reminders and are not used as assistant
        answers.
      </p>
    </section>
  </div>
)

export const SuggestedFaqInfo = ({ queue }: { queue: GapQueue | null }) => {
  const [open, setOpen] = useState(false)
  const show = useCallback(() => setOpen(true), [])
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="text-steel rounded-full"
        aria-label="How Suggested FAQs work"
        aria-haspopup="dialog"
        onClick={show}
      >
        <StateIcon name="info" className="size-5" />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>How Suggested FAQs work</DialogTitle>
            <DialogDescription>
              A list of repeated questions that need a better answer.
            </DialogDescription>
          </DialogHeader>
          <Explanation queue={queue} />
        </DialogContent>
      </Dialog>
    </>
  )
}
