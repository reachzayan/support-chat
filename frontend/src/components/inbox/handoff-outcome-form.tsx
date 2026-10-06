"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import { staffWrite } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import { FieldError } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"

export const HANDOFF_OUTCOMES = [
  {
    value: "resolved",
    label: "Resolved",
    description: "You answered the request or fixed the issue. No further follow-up is needed.",
  },
  {
    value: "callback_completed",
    label: "Callback completed",
    description:
      "You contacted the visitor outside this chat and completed the promised follow-up.",
  },
  {
    value: "no_response",
    label: "No response",
    description: "You tried to contact the visitor, but they did not reply.",
  },
  {
    value: "abandoned",
    label: "Abandoned",
    description: "The visitor left or withdrew the request before you could help.",
  },
]

type HandoffOutcomeFormProps = {
  handoffId: string
  onResolved: (payload: { outcome: string; note: string | null; resolved_at: string }) => void
}

const OutcomeChoices = ({
  handoffId,
  value,
  saving,
  onChange,
}: {
  handoffId: string
  value: string
  saving: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
}) => (
  <fieldset disabled={saving} className="grid gap-2 sm:grid-cols-2">
    <legend className="text-navy mb-2 text-sm font-bold">What happened?</legend>
    {HANDOFF_OUTCOMES.map((option) => (
      <label
        key={option.value}
        className="border-line has-checked:border-steel has-checked:bg-ice-2 has-focus-visible:ring-steel flex cursor-pointer gap-2 rounded-lg border p-3 has-focus-visible:ring-2"
      >
        <input
          type="radio"
          name={`handoff-outcome-${handoffId}`}
          value={option.value}
          checked={value === option.value}
          aria-label={option.label}
          aria-describedby={`handoff-${handoffId}-${option.value}`}
          onChange={onChange}
          className="accent-steel mt-0.5 shrink-0"
        />
        <span>
          <span className="text-navy block text-xs font-bold">{option.label}</span>
          <span
            id={`handoff-${handoffId}-${option.value}`}
            className="text-mute mt-1 block text-xs leading-5"
          >
            {option.description}
          </span>
        </span>
      </label>
    ))}
  </fieldset>
)

export const HandoffOutcomeForm = ({ handoffId, onResolved }: HandoffOutcomeFormProps) => {
  const [outcome, setOutcome] = useState("resolved")
  const [note, setNote] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const handleNote = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setNote(event.target.value.slice(0, 280))
  }, [])
  const handleOutcome = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => setOutcome(event.target.value),
    [],
  )

  const handleSubmit = useCallback(async () => {
    setSaving(true)
    setError(null)
    const response = await staffWrite(`/api/handoffs/${handoffId}/outcome`, "POST", {
      outcome,
      note: note.trim() || null,
    })
    setSaving(false)
    if (response.status === 409) {
      setError("This handoff is already resolved.")
      return
    }
    if (!response.ok) {
      setError("Could not save the outcome. Try again.")
      return
    }
    const body = (await response.json()) as {
      outcome: { outcome: string; note: string | null; resolved_at: string } | null
    }
    if (body.outcome) {
      onResolved(body.outcome)
    }
  }, [handoffId, note, onResolved, outcome])

  return (
    <div className="flex flex-col gap-2">
      <OutcomeChoices
        handoffId={handoffId}
        value={outcome}
        saving={saving}
        onChange={handleOutcome}
      />
      <p className="text-mute text-xs leading-5">
        Saving records an internal outcome and note. It does not contact the visitor or change the
        chat’s status. Use End chat to close the conversation.
      </p>
      <label
        className="text-mute text-[10px] font-semibold tracking-[0.12em] uppercase"
        htmlFor={`handoff-note-${handoffId}`}
      >
        Note (optional)
      </label>
      <Textarea
        id={`handoff-note-${handoffId}`}
        value={note}
        onChange={handleNote}
        maxLength={280}
        aria-label="Resolution note"
        placeholder="Short note for operations"
        className="min-h-16"
      />
      <FieldError>{error ?? undefined}</FieldError>
      <Button
        type="button"
        variant="default"
        size="lg"
        disabled={saving}
        onClick={handleSubmit}
        className="font-bold"
      >
        {saving ? <Spinner data-icon="inline-start" /> : null}
        {saving ? "Saving…" : "Save outcome"}
      </Button>
    </div>
  )
}
