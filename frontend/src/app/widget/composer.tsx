"use client"

import { ArrowUp } from "lucide-react"
import { useCallback, useState, type ChangeEvent, type FormEvent } from "react"

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
    <form onSubmit={handleSubmit} className="border-line bg-paper border-t px-5 py-4">
      <label className="sr-only" htmlFor="supportchat-message">
        Message
      </label>
      <div className="border-line focus-within:border-steel focus-within:ring-steel flex min-h-14 items-center gap-2 rounded-[8px] border bg-[#FAFBFD] px-3 py-2 transition-colors focus-within:ring-1">
        <input
          id="supportchat-message"
          name="message"
          autoComplete="off"
          disabled={disabled}
          placeholder="Write a message..."
          value={draft}
          onChange={handleDraftChange}
          className="text-ink placeholder:text-mute min-w-0 flex-1 bg-transparent px-1 text-base outline-none"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={!canSend}
          className="widget-send-button bg-steel text-paper hover:bg-navy disabled:bg-ember-soft focus-visible:ring-steel flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-[8px] focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed"
        >
          <ArrowUp aria-hidden="true" className="size-5" strokeWidth={2.4} />
          <span className="sr-only">Send</span>
        </button>
      </div>
    </form>
  )
}
