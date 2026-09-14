"use client"

import { ArrowUp } from "lucide-react"
import { useCallback, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

import type { CannedReply } from "./types"

type AgentComposerProps = {
  disabled: boolean
  closed?: boolean
  canned: CannedReply[]
  inputId: string
  onSend: (body: string) => void
}

export const expandCanned = (draft: string, canned: CannedReply[]) => {
  const trimmed = draft.trim()
  if (!trimmed.startsWith("#")) {
    return null
  }
  const match = canned.find((item) => item.shortcut === trimmed.slice(1))
  return match?.body ?? null
}

const composerPlaceholder = (closed: boolean, disabled: boolean) => {
  if (closed) {
    return "This chat is closed"
  }
  if (disabled) {
    return "Join this chat to reply"
  }
  return "Write a message..."
}

const ComposerField = ({
  closed,
  disabled,
  draft,
  inputId,
  canSend,
  onChange,
  onKeyDown,
}: {
  closed: boolean
  disabled: boolean
  draft: string
  inputId: string
  canSend: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void
}) => (
  <div
    className={`flex min-h-14 items-center gap-2 rounded-full border px-3 py-2 transition-[border-color,box-shadow,background-color] duration-150 ease-out ${
      closed
        ? "border-line text-mute bg-transparent"
        : "border-ink bg-paper shadow-[0_2px_8px_rgba(13,31,58,0.04)]"
    }`}
  >
    <Input
      id={inputId}
      name="message"
      autoComplete="off"
      value={draft}
      disabled={disabled}
      onChange={onChange}
      onKeyDown={onKeyDown}
      placeholder={composerPlaceholder(closed, disabled)}
      className="text-ink placeholder:text-mute disabled:text-mute h-auto min-w-0 flex-1 rounded-none border-0 !bg-transparent px-1 text-base shadow-none outline-none focus-visible:border-0 focus-visible:ring-0 dark:!bg-transparent"
    />
    <Button
      variant="default"
      size="icon-lg"
      type="submit"
      aria-label="Send"
      disabled={!canSend}
      className={`widget-send-button flex size-11 shrink-0 items-center justify-center rounded-full focus-visible:ring-2 focus-visible:outline-none ${
        closed
          ? "bg-line text-mute"
          : "bg-steel hover:bg-navy disabled:bg-ember-soft focus-visible:ring-steel dark:text-navy-deep text-white"
      }`}
    >
      <ArrowUp aria-hidden="true" className="size-5" strokeWidth={2.4} />
      <span className="sr-only">Send</span>
    </Button>
  </div>
)

export const AgentComposer = ({
  disabled,
  closed = false,
  canned,
  inputId,
  onSend,
}: AgentComposerProps) => {
  const [draft, setDraft] = useState("")
  const canSend = !disabled && draft.trim() !== ""

  const handleChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setDraft(event.target.value)
  }, [])

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      if (event.key !== "Tab" && event.key !== "Enter") {
        return
      }
      const expanded = expandCanned(draft, canned)
      if (expanded === null) {
        return
      }
      event.preventDefault()
      setDraft(expanded)
    },
    [canned, draft],
  )

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      if (disabled) {
        return
      }
      const expanded = expandCanned(draft, canned)
      if (expanded !== null) {
        setDraft(expanded)
        return
      }
      const body = draft.trim()
      if (body === "") {
        return
      }
      onSend(body)
      setDraft("")
    },
    [canned, disabled, draft, onSend],
  )

  return (
    <form
      onSubmit={handleSubmit}
      className={`border-line border-t px-5 py-4 ${closed ? "bg-ice-2" : "bg-ice"}`}
    >
      <label className="sr-only" htmlFor={inputId}>
        Message
      </label>
      <ComposerField
        closed={closed}
        disabled={disabled}
        draft={draft}
        inputId={inputId}
        canSend={canSend}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />
    </form>
  )
}
