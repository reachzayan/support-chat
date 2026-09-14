"use client"

import { ArrowUp } from "lucide-react"
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
    <form onSubmit={handleSubmit} className="border-line bg-paper border-t px-5 py-3.5">
      <label className="sr-only" htmlFor="supportchat-message">
        Message
      </label>
      <div className="border-line focus-within:border-steel focus-within:ring-steel bg-ice flex min-h-14 items-center gap-2 rounded-full border px-3 py-2 transition-[border-color,box-shadow] duration-150 ease-out focus-within:ring-2">
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
          className="widget-send-button bg-steel hover:bg-navy disabled:bg-ember-soft focus-visible:ring-steel dark:text-navy-deep flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-white focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed"
        >
          <ArrowUp aria-hidden="true" className="size-5" strokeWidth={2.4} />
          <span className="sr-only">Send</span>
        </Button>
      </div>
    </form>
  )
}
