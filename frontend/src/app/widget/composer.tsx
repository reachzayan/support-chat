/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

"use client"

import { motion, useReducedMotion } from "motion/react"
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StateIcon } from "@/components/ui/state-icon"

type ComposerProps = {
  disabled: boolean
  sending: boolean
  replying?: boolean
  sendError?: string
  onSend: (body: string) => boolean
}

const SEND_ERROR_COPY: Record<string, string> = {
  assistant_busy: "Still answering your last message. Send again when it finishes.",
  rate_limited: "You're sending messages quickly. Wait a moment and try again.",
}
const SEND_ERROR_FALLBACK = "Your message was not sent. Try again."
const REPLYING_HINT = "Wait for the reply to finish"

const SendNotice = ({ code }: { code?: string }) =>
  code ? (
    <output
      aria-live="polite"
      className="widget-enter text-mute mb-2 flex items-center gap-2 rounded-2xl bg-white/66 px-3 py-2.5 text-xs font-semibold shadow-[0_6px_18px_rgba(13,31,58,0.06)] backdrop-blur-xl"
    >
      <span className="bg-ember size-1.5 shrink-0 rounded-full" />
      {SEND_ERROR_COPY[code] ?? SEND_ERROR_FALLBACK}
    </output>
  ) : null

const useDraftClearedOnAck = (
  sending: boolean,
  sendError: string | undefined,
  setDraft: (update: (current: string) => string) => void,
) => {
  const submittedRef = useRef<string | null>(null)
  const wasSendingRef = useRef(false)
  // The draft stays until the server acks; an error frame leaves it for retry.
  useEffect(() => {
    const finished = wasSendingRef.current && !sending
    wasSendingRef.current = sending
    if (finished && sendError === undefined && submittedRef.current !== null) {
      const submitted = submittedRef.current
      submittedRef.current = null
      setDraft((current) => (current.trim() === submitted ? "" : current))
    }
  }, [sending, sendError, setDraft])
  return submittedRef
}

export const Composer = ({
  disabled,
  sending,
  replying = false,
  sendError,
  onSend,
}: ComposerProps) => {
  const [draft, setDraft] = useState("")
  const reducedMotion = useReducedMotion()
  const submittedRef = useDraftClearedOnAck(sending, sendError, setDraft)
  const canSend = !disabled && !sending && !replying && draft.trim() !== ""
  const handleDraftChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setDraft(event.target.value)
  }, [])
  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const body = draft.trim()
      if (!canSend) {
        return
      }
      if (onSend(body)) {
        submittedRef.current = body
      }
    },
    [canSend, draft, onSend, submittedRef],
  )

  return (
    <form onSubmit={handleSubmit} className="bg-transparent px-3 pt-2 pb-2 sm:pb-3">
      <SendNotice code={sendError} />
      <label className="sr-only" htmlFor="supportchat-message">
        Message
      </label>
      <motion.div
        layout
        transition={
          reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32 }
        }
        className="focus-within:border-steel/45 focus-within:ring-steel/25 border-line flex min-h-14 items-center gap-2 rounded-2xl border bg-white/80 px-3 py-2 shadow-[0_1px_2px_rgba(13,31,58,0.04)] backdrop-blur-xl transition-[border-color,box-shadow] duration-200 ease-out focus-within:ring-4"
      >
        <Input
          id="supportchat-message"
          name="message"
          autoComplete="off"
          disabled={disabled}
          placeholder="Write a message..."
          value={draft}
          onChange={handleDraftChange}
          className="text-ink placeholder:text-mute h-auto min-h-11 min-w-0 flex-1 rounded-none border-0 !bg-transparent px-1 text-base! shadow-none outline-none focus-visible:border-0 focus-visible:ring-0 dark:!bg-transparent"
        />
        <Button
          variant="secondary"
          size="icon-lg"
          type="submit"
          aria-label="Send"
          aria-describedby={replying ? "supportchat-reply-hint" : undefined}
          disabled={!canSend}
          className="widget-send-button border-steel/15 bg-ice-2 text-navy hover:!text-navy focus-visible:ring-steel/30 hover:bg-ice-2! flex size-11 shrink-0 rounded-full border focus-visible:ring-4 disabled:opacity-45"
        >
          <StateIcon name="arrow-up" className="size-5" />
          <span className="sr-only">Send</span>
        </Button>
      </motion.div>
      {replying ? (
        <span id="supportchat-reply-hint" className="sr-only">
          {REPLYING_HINT}
        </span>
      ) : null}
    </form>
  )
}
