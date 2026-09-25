"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop -- Base UI composes shadcn buttons through render. */
/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- callbacks are scoped to a tiny list */
/* oxlint-disable max-lines-per-function -- the compact history surface is one cohesive state */

import { CalendarDays, Check, History, ShieldCheck } from "lucide-react"
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

const PRIMARY =
  "border-steel/15 bg-ice-2 text-navy hover:!bg-[#e6eefc] hover:!text-navy focus-visible:ring-steel/30 min-h-11 w-full border px-4 text-sm font-bold leading-none shadow-[0_8px_20px_rgba(36,86,160,0.12)] focus-visible:ring-4"

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
          <Button
            type="button"
            variant="secondary"
            className={PRIMARY}
            onClick={props.onShowHistory}
          >
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
  const [confirmReplace, setConfirmReplace] = useState(false)
  const selected = conversations.find((item) => item.id === selectedId) ?? conversations[0]
  const hasDifferentCurrent = conversations.some(
    (item) => item.is_current && item.id !== selected?.id,
  )
  const formatter = useMemo(
    () => new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }),
    [],
  )
  const openSelected = () => {
    if (!selected) return
    if (!selected.is_current && hasDifferentCurrent) {
      setConfirmReplace(true)
      return
    }
    onOpen(selected.id, false)
  }

  return (
    <section className="widget-enter flex min-h-0 flex-1 flex-col px-4 pt-3 pb-4">
      <div className="px-1">
        <div className="text-steel mb-2 flex items-center gap-2 text-xs font-bold tracking-[0.16em] uppercase">
          <History aria-hidden="true" className="size-4" />
          Same browser history
        </div>
        <h2 className="heading text-navy text-2xl">Your chats</h2>
        <p className="text-mute mt-1 text-sm">Choose a conversation to continue.</p>
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
                aria-label={`${label}, ${status}, ${formatter.format(new Date(conversation.last_message_at))}`}
                aria-pressed={selectedRow}
                onClick={() => setSelectedId(conversation.id)}
                className={`focus-visible:ring-steel flex min-h-[72px] w-full cursor-pointer items-center gap-3 rounded-2xl border p-3 text-left focus-visible:ring-2 focus-visible:outline-none ${
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
                  <span className="text-mute mt-1 block text-xs">
                    {status} · {formatter.format(new Date(conversation.last_message_at))}
                  </span>
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
          variant="secondary"
          className={PRIMARY}
          disabled={!selected}
          onClick={openSelected}
        >
          {selected?.is_current ? "Continue chat" : "Resume chat"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="text-steel hover:!bg-ice-2/80 hover:!text-navy focus-visible:ring-steel min-h-10 w-full cursor-pointer rounded-xl text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
          onClick={onStartFresh}
        >
          Start fresh instead
        </Button>
      </div>
      <AlertDialog open={confirmReplace} onOpenChange={setConfirmReplace}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Resume this chat instead?</AlertDialogTitle>
            <AlertDialogDescription className="text-mute mt-2 text-sm leading-5">
              Your current chat will close and stay in history. The selected chat will reopen.
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
              onClick={() => selected && onOpen(selected.id, true)}
            >
              Resume chat
            </AlertDialogClose>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
