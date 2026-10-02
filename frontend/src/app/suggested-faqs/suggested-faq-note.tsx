"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Note handlers close over this question and draft. */

import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"

import type { GapRecord } from "./suggested-faq-model"

const NOTE_MAX = 1000
const NOTE_ERROR = "The note could not be saved. Try again."

export const GapNote = ({
  gap,
  onSave,
}: {
  gap: GapRecord
  onSave: (gap: GapRecord, note: string) => Promise<boolean>
}) => {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(gap.note ?? "")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    setError("")
    const saved = await onSave(gap, draft.trim())
    setSaving(false)
    if (saved) setEditing(false)
    else setError(NOTE_ERROR)
  }

  const handleCancel = () => {
    setDraft(gap.note ?? "")
    setError("")
    setEditing(false)
  }

  if (!editing) {
    return (
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        {gap.note ? (
          <p className="text-ink text-sm">
            <span className="font-semibold">Note for the website team: </span>
            {gap.note}
          </p>
        ) : null}
        <Button
          type="button"
          variant="link"
          size="sm"
          aria-label={`${gap.note ? "Edit note" : "Add note"}: ${gap.question}`}
          onClick={() => setEditing(true)}
        >
          {gap.note ? "Edit note" : "Add note for the website team"}
        </Button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-2">
      <label htmlFor={`note-${gap.id}`} className="text-ink text-xs font-semibold">
        Note for the website team
      </label>
      <Textarea
        id={`note-${gap.id}`}
        value={draft}
        maxLength={NOTE_MAX}
        rows={2}
        onChange={(event) => setDraft(event.target.value)}
      />
      {error ? (
        <p className="text-ember text-xs" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? <Spinner data-icon="inline-start" /> : null}
          Save note
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
