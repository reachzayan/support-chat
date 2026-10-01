"use client"

/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-function-as-prop, eslint/complexity -- Base UI render props and picker item handlers depend on live composer state; the keyboard map is deliberately a single reviewable interaction contract. */

import { ArrowUp, Hash } from "lucide-react"
import Link from "next/link"
import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

import type { CannedReply } from "./types"

export type CannedVariables = {
  customerName?: string | null
  customerEmail?: string | null
  agentName?: string | null
  agentEmail?: string | null
}

type AgentComposerProps = {
  disabled: boolean
  closed?: boolean
  canned: CannedReply[]
  inputId: string
  variables?: CannedVariables
  onSend: (body: string) => boolean
}

const EMPTY_VARIABLES: CannedVariables = {}

export const fillCannedVariables = (body: string, variables: CannedVariables = EMPTY_VARIABLES) => {
  return body
    .replaceAll("%customer-name%", (variables.customerName ?? "").trim())
    .replaceAll("%customer-email%", (variables.customerEmail ?? "").trim())
    .replaceAll("%agent-name%", (variables.agentName ?? "").trim())
    .replaceAll("%agent-email%", (variables.agentEmail ?? "").trim())
}

const matchesCannedToken = (item: CannedReply, token: string) =>
  item.shortcut === token || (item.aliases ?? []).includes(token)

export const expandCanned = (
  draft: string,
  canned: CannedReply[],
  variables: CannedVariables = EMPTY_VARIABLES,
) => {
  const trimmed = draft.trim()
  if (!trimmed.startsWith("#")) {
    return null
  }
  const match = canned.find((item) => matchesCannedToken(item, trimmed.slice(1).toLowerCase()))
  return match ? fillCannedVariables(match.body, variables) : null
}

const COMPOSER_MAX_HEIGHT_PX = 168

const composerPlaceholder = (closed: boolean, disabled: boolean) => {
  if (closed) {
    return "This chat is closed"
  }
  if (disabled) {
    return "Join this chat to reply"
  }
  return "Write a message..."
}

const resizeComposerField = (field: HTMLTextAreaElement | null) => {
  if (!field) {
    return
  }
  field.style.height = "0px"
  field.style.height = `${Math.min(field.scrollHeight, COMPOSER_MAX_HEIGHT_PX)}px`
}

// oxlint-disable-next-line eslint/max-lines-per-function, eslint/complexity -- Keyboard navigation and canned picker state stay with the textarea markup.
const ComposerField = ({
  closed,
  disabled,
  draft,
  inputId,
  canSend,
  canned,
  pickerOpen,
  activeIndex,
  onOpenPicker,
  onPickerOpenChange,
  onSelect,
  inputRef,
  onChange,
  onKeyDown,
}: {
  closed: boolean
  disabled: boolean
  draft: string
  inputId: string
  canSend: boolean
  canned: CannedReply[]
  pickerOpen: boolean
  activeIndex: number
  onOpenPicker: () => void
  onPickerOpenChange: (open: boolean) => void
  onSelect: (item: CannedReply) => void
  inputRef: RefObject<HTMLTextAreaElement | null>
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}) => (
  <div
    className={`relative flex min-h-14 items-end gap-2 rounded-2xl border px-3 py-2 transition-[border-color,box-shadow,background-color,opacity] duration-150 ease-out ${
      closed
        ? "border-line text-mute bg-transparent"
        : disabled
          ? "border-line bg-ice-2/90 text-mute cursor-not-allowed opacity-75 shadow-none"
          : "border-ink bg-paper shadow-[0_2px_8px_rgba(13,31,58,0.04)]"
    }`}
  >
    <Popover open={pickerOpen} onOpenChange={onPickerOpenChange} triggerId="canned-picker-trigger">
      <PopoverTrigger
        id="canned-picker-trigger"
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            aria-label="Open canned responses"
            disabled={disabled}
            onClick={onOpenPicker}
            className={disabled ? "text-mute/70 mb-0.5" : "mb-0.5"}
          />
        }
      >
        <Hash aria-hidden="true" className="size-4" />
      </PopoverTrigger>
      <PopoverContent initialFocus={false} finalFocus={false} className="overflow-hidden">
        <div className="border-line flex items-center justify-between border-b px-3 py-2">
          <p className="text-navy heading text-xs">Canned responses</p>
          <Link
            href="/admin/canned-responses"
            className="text-steel text-xs font-bold underline underline-offset-2"
          >
            Manage canned responses
          </Link>
        </div>
        {canned.length === 0 ? (
          <p className="text-mute px-3 py-4 text-sm">
            No canned responses are available for this website.
          </p>
        ) : (
          <div className="max-h-64 overflow-y-auto p-1">
            {canned.map((item, index) => (
              <button
                key={item.shortcut}
                type="button"
                onClick={() => onSelect(item)}
                aria-label={`Insert #${item.shortcut}`}
                className={`flex w-full flex-col items-start justify-start gap-0.5 rounded-[8px] px-3 py-2 text-left transition-[background-color] duration-150 ${index === activeIndex ? "bg-ice-2" : "hover:bg-ice"}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="text-steel font-mono text-xs font-bold">#{item.shortcut}</span>
                  <span className="text-mute bg-paper shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase">
                    {item.scope}
                  </span>
                </span>
                {(item.aliases ?? []).length > 0 ? (
                  <span className="text-mute font-mono text-[10px]">
                    {(item.aliases ?? []).map((alias) => `#${alias}`).join(" ")}
                  </span>
                ) : null}
                <span className="text-mute line-clamp-1 w-full text-xs leading-snug whitespace-normal">
                  {item.body}
                </span>
              </button>
            ))}
          </div>
        )}
      </PopoverContent>
    </Popover>
    <textarea
      ref={inputRef}
      id={inputId}
      name="message"
      rows={1}
      autoComplete="off"
      value={draft}
      disabled={disabled}
      onChange={onChange}
      onKeyDown={onKeyDown}
      placeholder={composerPlaceholder(closed, disabled)}
      className="text-ink placeholder:text-mute/80 disabled:text-mute/80 max-h-42 min-h-6 min-w-0 flex-1 resize-none overflow-y-auto rounded-none border-0 !bg-transparent px-1 py-2.5 text-base leading-6 shadow-none outline-none focus-visible:border-0 focus-visible:ring-0 disabled:cursor-not-allowed dark:!bg-transparent"
    />
    <Button
      variant="ghost"
      size="icon-lg"
      type="submit"
      aria-label="Send"
      disabled={!canSend}
      className={`widget-send-button mb-0.5 flex size-11 shrink-0 items-center justify-center rounded-full focus-visible:ring-2 focus-visible:outline-none ${
        closed
          ? "bg-line text-mute"
          : disabled
            ? "bg-line text-mute/80 cursor-not-allowed"
            : "bg-steel hover:bg-navy disabled:bg-ember-soft focus-visible:ring-steel text-white hover:text-white"
      }`}
    >
      <ArrowUp aria-hidden="true" className="size-5" strokeWidth={2.4} />
      <span className="sr-only">Send</span>
    </Button>
  </div>
)

// oxlint-disable-next-line eslint/max-lines-per-function, eslint/complexity -- Keyboard navigation and send semantics are intentionally co-located in the composer.
export const AgentComposer = ({
  disabled,
  closed = false,
  canned,
  inputId,
  variables = EMPTY_VARIABLES,
  onSend,
}: AgentComposerProps) => {
  const [draft, setDraft] = useState("")
  const [pickerOpen, setPickerOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const canSend = !disabled && draft.trim() !== ""
  const results = useMemo(() => {
    const query = draft.startsWith("#") ? draft.slice(1).toLowerCase() : ""
    return [...canned]
      .filter((item) => {
        if (!query) return true
        const haystack = [item.shortcut, ...(item.aliases ?? []), item.body.toLowerCase()]
        return haystack.some((value) => value.includes(query))
      })
      .toSorted((left, right) => {
        const leftRank =
          left.shortcut.startsWith(query) ||
          (left.aliases ?? []).some((alias) => alias.startsWith(query))
            ? 0
            : 1
        const rightRank =
          right.shortcut.startsWith(query) ||
          (right.aliases ?? []).some((alias) => alias.startsWith(query))
            ? 0
            : 1
        return leftRank - rightRank || left.shortcut.localeCompare(right.shortcut)
      })
  }, [canned, draft])

  useLayoutEffect(() => {
    resizeComposerField(inputRef.current)
    // Remeasure after the controlled draft paints; draft is the trigger, not a value read here.
    // oxlint-disable-next-line react/exhaustive-effect-dependencies
  }, [draft])

  const selectCanned = useCallback(
    (item: CannedReply) => {
      setDraft(fillCannedVariables(item.body, variables))
      setPickerOpen(false)
      setActiveIndex(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    },
    [variables],
  )

  const handleChange = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    const value = event.target.value
    setDraft(value)
    if (value.startsWith("#")) {
      setPickerOpen(true)
      setActiveIndex(0)
    } else {
      setPickerOpen(false)
    }
  }, [])

  // oxlint-disable-next-line eslint/complexity -- The compact keyboard contract maps directly to the picker actions.
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Escape" && pickerOpen) {
        event.preventDefault()
        setPickerOpen(false)
        return
      }
      if (pickerOpen && event.key === "ArrowDown") {
        event.preventDefault()
        setActiveIndex((current) => Math.min(current + 1, Math.max(results.length - 1, 0)))
        return
      }
      if (pickerOpen && event.key === "ArrowUp") {
        event.preventDefault()
        setActiveIndex((current) => Math.max(current - 1, 0))
        return
      }
      if (event.key === "Enter" && event.shiftKey) {
        return
      }
      if (event.key !== "Tab" && event.key !== "Enter") {
        return
      }
      const expanded = expandCanned(draft, canned, variables)
      if (expanded !== null) {
        event.preventDefault()
        setDraft(expanded)
        setPickerOpen(false)
        return
      }
      if (pickerOpen && results[activeIndex]) {
        event.preventDefault()
        selectCanned(results[activeIndex])
        return
      }
      if (event.key === "Enter") {
        event.preventDefault()
        event.currentTarget.form?.requestSubmit()
      }
    },
    [activeIndex, canned, draft, pickerOpen, results, selectCanned, variables],
  )

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      if (disabled) {
        return
      }
      const expanded = expandCanned(draft, canned, variables)
      if (expanded !== null) {
        setDraft(expanded)
        return
      }
      const body = fillCannedVariables(draft.trim(), variables)
      if (body === "") {
        return
      }
      if (onSend(body)) {
        setDraft("")
      }
    },
    [canned, disabled, draft, onSend, variables],
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
        canned={results}
        pickerOpen={pickerOpen}
        activeIndex={activeIndex}
        onOpenPicker={() => setPickerOpen(true)}
        onPickerOpenChange={setPickerOpen}
        onSelect={selectCanned}
        inputRef={inputRef}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />
    </form>
  )
}
