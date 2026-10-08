"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- Base UI composes shadcn buttons through render. */
/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- callbacks are scoped to a tiny list */
/* oxlint-disable max-lines-per-function -- the compact history surface is one cohesive state */

import { CalendarDays, Check, ShieldCheck } from "lucide-react"
import { useMemo, useState } from "react"

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
import type { ConversationHistoryItem, ReturningIdentity } from "@/lib/postmessage"

import { CTA_BUTTON } from "./cta-button"

const INQUIRY_LABELS: Record<string, string> = {
  sales: "Sales question",
  results: "Results question",
  portal: "Portal help",
  compliance: "Compliance question",
  other: "General question",
}

type ReturningHomeProps =
  | {
      mode: "identity"
      identity: ReturningIdentity
      onShowHistory: () => void
      onStartFresh: () => void
    }
  | {
      mode: "history"
      identity: ReturningIdentity
      conversations: ConversationHistoryItem[]
      onOpen: (conversationId: string, replaceCurrent: boolean) => void
      onStartFresh: () => void
    }

const PRIMARY = CTA_BUTTON

const QUIET =
  "text-steel hover:!bg-ice-2/80 hover:!text-navy focus-visible:ring-steel min-h-11 w-full cursor-pointer rounded-2xl text-sm font-bold focus-visible:ring-2 focus-visible:outline-none"

export const ReturningHome = (props: ReturningHomeProps) => {
  if (props.mode === "identity") {
    return (
      <section className="widget-enter flex min-h-0 flex-1 flex-col px-5 pt-5 pb-4">
        <div className="bg-ice text-steel mb-5 flex size-11 items-center justify-center rounded-2xl">
          <ShieldCheck aria-hidden="true" className="size-6" />
        </div>
        <h2 className="heading text-navy text-2xl">Is this you?</h2>
        <p className="text-mute mt-2 text-sm leading-6">
          We found chat history saved for this browser. Confirm before we show it.
        </p>
        <div className="border-line mt-5 rounded-2xl border bg-white p-4 shadow-[0_10px_28px_rgba(13,31,58,0.08)]">
          <p className="heading text-ink truncate text-base" title={props.identity.display_name}>
            {props.identity.display_name}
          </p>
          <p className="text-mute mt-1 truncate text-sm" title={props.identity.email_hint}>
            {props.identity.email_hint}
          </p>
          {props.identity.phone_hint ? (
            <p className="text-mute mt-1 text-sm">{props.identity.phone_hint}</p>
          ) : null}
          <p className="text-steel mt-3 text-xs font-bold">
            {props.identity.chat_count} saved {props.identity.chat_count === 1 ? "chat" : "chats"}
          </p>
        </div>
        <div className="mt-auto space-y-2 pt-6">
          <Button type="button" variant="default" className={PRIMARY} onClick={props.onShowHistory}>
            Yes, show my chats
          </Button>
          <Button type="button" variant="ghost" className={QUIET} onClick={props.onStartFresh}>
            No, start fresh
          </Button>
        </div>
      </section>
    )
  }
  return <HistoryList {...props} />
}

const HistoryList = ({
  conversations,
  onOpen,
  onStartFresh,
}: Extract<ReturningHomeProps, { mode: "history" }>) => {
  const [selectedId, setSelectedId] = useState(conversations[0]?.id ?? "")
  const [confirmation, setConfirmation] = useState<"resume" | "new" | null>(null)
  const selected = conversations.find((item) => item.id === selectedId) ?? conversations[0]
  const hasDifferentCurrent = conversations.some(
    (item) => item.is_current && item.id !== selected?.id,
  )
  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }),
    [],
  )
  const openSelected = () => {
    if (!selected) return
    if (!selected.is_current && hasDifferentCurrent) {
      setConfirmation("resume")
      return
    }
    onOpen(selected.id, false)
  }

  return (
    <section className="widget-enter flex min-h-0 flex-1 flex-col px-4 pt-3 pb-4">
      <div className="px-1">
        <h2 className="heading text-navy text-2xl">Your chats</h2>
        <p className="text-mute mt-1 text-sm">Continue a conversation or start a new chat.</p>
      </div>
      <ul className="mt-4 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {conversations.map((conversation) => {
          const selectedRow = conversation.id === selected?.id
          const label = INQUIRY_LABELS[conversation.inquiry_type ?? "other"] ?? "General question"
          const status = conversation.is_current ? "Current chat" : "Past chat"
          return (
            <li key={conversation.id}>
              <Button
                type="button"
                variant="ghost"
                aria-label={`${label}, ${status}, ${formatter.format(new Date(conversation.last_message_at))}${conversation.preview ? `, ${conversation.preview}` : ""}`}
                aria-pressed={selectedRow}
                onClick={() => setSelectedId(conversation.id)}
                className={`focus-visible:ring-steel flex !h-auto min-h-[72px] w-full cursor-pointer items-start gap-3 rounded-2xl border p-3 text-left !whitespace-normal focus-visible:ring-2 focus-visible:outline-none ${
                  selectedRow
                    ? "border-steel bg-ice shadow-[0_8px_20px_rgba(36,86,160,0.10)]"
                    : "border-line hover:bg-ice/60 bg-white"
                }`}
              >
                <span className="bg-paper text-steel flex size-10 shrink-0 items-center justify-center rounded-xl">
                  <CalendarDays aria-hidden="true" className="size-5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="heading text-ink block truncate text-sm">{label}</span>
                  {conversation.preview ? (
                    <span className="text-ink mt-1 line-clamp-2 text-sm leading-5 break-words">
                      {conversation.preview}
                    </span>
                  ) : null}
                  <span className="text-mute mt-1.5 block text-xs leading-5">
                    {status} · {formatter.format(new Date(conversation.last_message_at))}
                  </span>
                  {conversation.assigned_agent ? (
                    <span className="text-mute block truncate text-xs leading-5">
                      With {conversation.assigned_agent.display_name}
                    </span>
                  ) : null}
                </span>
                {selectedRow ? (
                  <Check aria-hidden="true" className="text-steel size-5 shrink-0" />
                ) : null}
              </Button>
            </li>
          )
        })}
      </ul>
      <div className="mt-3 space-y-1.5">
        <Button
          type="button"
          variant="default"
          className={PRIMARY}
          disabled={!selected}
          onClick={openSelected}
        >
          {selected?.is_current ? "Continue chat" : "Resume chat"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className={QUIET}
          onClick={() =>
            conversations.some((item) => item.is_current) ? setConfirmation("new") : onStartFresh()
          }
        >
          Start a new chat
        </Button>
      </div>
      <AlertDialog
        open={confirmation !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmation(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmation === "new" ? "Start a new chat?" : "Resume this chat instead?"}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-mute mt-2 text-sm leading-5">
              {confirmation === "new"
                ? "Your current chat will close and stay in history. Your contact details will carry over to the new chat."
                : "Your current chat will close and stay in history. The selected chat will reopen."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogClose
              render={<Button variant="outline" className="min-h-10 px-4 font-bold" />}
            >
              Cancel
            </AlertDialogClose>
            <AlertDialogClose
              render={<Button variant="default" className="min-h-10 px-4 font-bold" />}
              onClick={() =>
                confirmation === "new" ? onStartFresh() : selected && onOpen(selected.id, true)
              }
            >
              {confirmation === "new" ? "Start new chat" : "Resume chat"}
            </AlertDialogClose>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
