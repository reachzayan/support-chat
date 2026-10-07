/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

"use client"

import { motion, useReducedMotion } from "motion/react"
import { useCallback, useState, type ChangeEvent, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StateIcon } from "@/components/ui/state-icon"

type ComposerProps = {
  disabled: boolean
  sending: boolean
  onSend: (body: string) => boolean
}

export const Composer = ({ disabled, sending, onSend }: ComposerProps) => {
  const [draft, setDraft] = useState("")
  const reducedMotion = useReducedMotion()
  const canSend = !disabled && !sending && draft.trim() !== ""
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
        setDraft("")
      }
    },
    [canSend, draft, onSend],
  )

  return (
    <form onSubmit={handleSubmit} className="bg-transparent px-3 pt-2 pb-3">
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
          className="text-ink placeholder:text-mute h-auto min-w-0 flex-1 rounded-none border-0 !bg-transparent px-1 text-base shadow-none outline-none focus-visible:border-0 focus-visible:ring-0 dark:!bg-transparent"
        />
        <Button
          variant="secondary"
          size="icon-lg"
          type="submit"
          aria-label="Send"
          disabled={!canSend}
          className="widget-send-button border-steel/15 bg-ice-2 text-navy hover:!text-navy focus-visible:ring-steel/30 hover:bg-ice-2! flex size-10 shrink-0 rounded-full border focus-visible:ring-4 disabled:opacity-45"
        >
          <StateIcon name="arrow-up" className="size-5" />
          <span className="sr-only">Send</span>
        </Button>
      </motion.div>
    </form>
  )
}
