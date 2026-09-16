/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

"use client"

import { ArrowUp } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import { useCallback, useState, type ChangeEvent, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type ComposerProps = {
  disabled: boolean
  sending: boolean
  onSend: (body: string) => void
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
      onSend(body)
      setDraft("")
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
        className="focus-within:border-steel/45 focus-within:ring-steel/25 flex min-h-14 items-center gap-2 rounded-[28px] border border-white/80 bg-white/80 px-3 py-2 shadow-[0_10px_30px_rgba(13,31,58,0.12)] backdrop-blur-xl transition-[border-color,box-shadow] duration-200 ease-out focus-within:ring-4"
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
          variant="default"
          size="icon-lg"
          type="submit"
          aria-label="Send"
          disabled={!canSend}
          className="widget-send-button bg-ember hover:bg-ember-mid disabled:bg-ember-soft focus-visible:ring-ember/30 flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-white focus-visible:ring-4 focus-visible:outline-none disabled:cursor-not-allowed"
        >
          <ArrowUp aria-hidden="true" className="size-5" strokeWidth={2.4} />
          <span className="sr-only">Send</span>
        </Button>
      </motion.div>
    </form>
  )
}
