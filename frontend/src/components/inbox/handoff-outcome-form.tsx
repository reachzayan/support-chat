"use client"

import { useCallback, useState, type ChangeEvent } from "react"

import { staffWrite } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import { FieldError } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup } from "@/components/ui/toggle-group"

const OUTCOMES = [
  { value: "resolved", label: "Resolved" },
  { value: "callback_completed", label: "Callback done" },
  { value: "no_response", label: "No response" },
  { value: "abandoned", label: "Abandoned" },
]

type HandoffOutcomeFormProps = {
  handoffId: string
  onResolved: (payload: { outcome: string; note: string | null; resolved_at: string }) => void
}

export const HandoffOutcomeForm = ({ handoffId, onResolved }: HandoffOutcomeFormProps) => {
  const [outcome, setOutcome] = useState("resolved")
  const [note, setNote] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const handleNote = useCallback((event: ChangeEvent<HTMLTextAreaElement>) => {
    setNote(event.target.value.slice(0, 280))
  }, [])

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
      <ToggleGroup
        aria-label="Handoff outcome"
        value={outcome}
        onValueChange={setOutcome}
        options={OUTCOMES}
      />
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
        disabled={saving}
        onClick={handleSubmit}
        className="bg-ember hover:bg-ember-mid focus-visible:ring-steel dark:text-navy-deep h-9 rounded-[8px] px-4 text-sm font-bold text-white"
      >
        Resolve handoff
      </Button>
    </div>
  )
}
