"use client"

/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Controlled form handlers close over the current draft. */

import Link from "next/link"
import { useState, type FormEvent } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"

import {
  ANSWER_MAX,
  KNOWLEDGE_HREF,
  cannedEditHref,
  recommendedKind,
  suggestShortcut,
  type AnswerKind,
  type AnswerPayload,
  type GapRecord,
  type SimilarEntries,
} from "./suggested-faq-model"

type AnswerDialogProps = {
  gap: GapRecord | null
  isAdmin: boolean
  replies: string[]
  similar: SimilarEntries | null
  submitting: boolean
  error: string
  onClose: () => void
  onSubmit: (payload: AnswerPayload) => void
}

const FIELD_CLASS =
  "border-line bg-ice text-ink focus-visible:ring-steel h-10 rounded-[8px] border px-3 text-sm outline-none focus-visible:ring-2"

const KindOption = ({
  value,
  title,
  hint,
  checked,
  recommended,
  disabled = false,
  onSelect,
}: {
  value: AnswerKind
  title: string
  hint: string
  checked: boolean
  recommended: boolean
  disabled?: boolean
  onSelect: (value: AnswerKind) => void
}) => (
  <label className="border-line bg-ice has-checked:border-steel has-checked:bg-ice-2 has-focus-visible:ring-steel flex cursor-pointer flex-col gap-0.5 rounded-[8px] border px-3 py-2.5 has-focus-visible:ring-2 has-disabled:cursor-not-allowed has-disabled:opacity-60">
    <input
      type="radio"
      name="answer-kind"
      value={value}
      checked={checked}
      disabled={disabled}
      onChange={() => onSelect(value)}
      className="sr-only"
    />
    <span className="flex items-center gap-2">
      <span className="text-navy text-sm font-semibold">{title}</span>
      {recommended ? <Badge className="bg-ice-2 text-steel">Recommended</Badge> : null}
    </span>
    <span className="text-mute text-xs">{hint}</span>
  </label>
)

const KindFieldset = ({
  kind,
  recommended,
  isAdmin,
  onSelect,
}: {
  kind: AnswerKind
  recommended: AnswerKind
  isAdmin: boolean
  onSelect: (value: AnswerKind) => void
}) => (
  <fieldset className="flex flex-col gap-2">
    <legend className="text-ink mb-1.5 text-sm font-medium">Save it as</legend>
    <KindOption
      value="canned"
      title="Quick reply"
      hint="Specialists insert it with #shortcut. The assistant sends it word for word."
      checked={kind === "canned"}
      recommended={recommended === "canned"}
      onSelect={onSelect}
    />
    <KindOption
      value="knowledge"
      title="Knowledge text"
      hint="Longer reference. The assistant answers from it and cites it."
      checked={kind === "knowledge"}
      recommended={recommended === "knowledge"}
      disabled={!isAdmin}
      onSelect={onSelect}
    />
    {isAdmin ? null : <p className="text-mute text-xs">Only admins can add knowledge text.</p>}
  </fieldset>
)

const NameField = ({
  kind,
  shortcut,
  title,
  onShortcut,
  onTitle,
}: {
  kind: AnswerKind
  shortcut: string
  title: string
  onShortcut: (value: string) => void
  onTitle: (value: string) => void
}) =>
  kind === "canned" ? (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="suggested-faq-shortcut" className="text-ink text-sm font-medium">
        Shortcut
      </label>
      <span className="border-line bg-ice flex h-10 items-center rounded-[8px] border px-3">
        <span aria-hidden="true" className="text-mute font-mono">
          #
        </span>
        <input
          id="suggested-faq-shortcut"
          value={shortcut}
          maxLength={40}
          onChange={(event) => onShortcut(event.target.value)}
          className="text-ink min-w-0 flex-1 bg-transparent p-0 font-mono text-sm outline-none focus-visible:ring-0"
        />
      </span>
    </div>
  ) : (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="suggested-faq-title" className="text-ink text-sm font-medium">
        Title
      </label>
      <input
        id="suggested-faq-title"
        value={title}
        maxLength={300}
        onChange={(event) => onTitle(event.target.value)}
        className={FIELD_CLASS}
      />
    </div>
  )

const LINK_CLASS =
  "text-steel focus-visible:ring-steel text-sm font-medium underline-offset-2 outline-none hover:underline focus-visible:ring-2"

const ClosestEntries = ({ similar }: { similar: SimilarEntries | null }) => {
  if (!similar || (!similar.canned && !similar.knowledge)) return null
  const { canned, knowledge } = similar
  return (
    <section
      aria-labelledby="closest-entries-title"
      className="border-ember/40 bg-ice flex flex-col gap-2 rounded-[8px] border p-3"
    >
      <div>
        <h3 id="closest-entries-title" className="text-ink text-sm font-medium">
          Already close to this
        </h3>
        <p className="text-mute text-xs">
          Editing the existing answer usually beats adding a second one for the same question.
        </p>
      </div>
      {canned ? (
        <div className="flex flex-col items-start gap-1">
          <p className="text-ink text-sm">{canned.excerpt}</p>
          {canned.bot_eligible ? null : <Badge className="bg-ice-2 text-mute">Staff only</Badge>}
          <Link href={cannedEditHref(canned)} className={LINK_CLASS}>
            Edit #{canned.shortcut} instead
          </Link>
        </div>
      ) : null}
      {knowledge ? (
        <div className="flex flex-col items-start gap-1">
          <p className="text-ink text-sm font-medium">{knowledge.title}</p>
          <p className="text-mute text-xs break-all">{knowledge.url}</p>
          <Link href={KNOWLEDGE_HREF} className={LINK_CLASS}>
            Open the knowledge base
          </Link>
        </div>
      ) : null}
    </section>
  )
}

const SpecialistReplies = ({
  replies,
  onUse,
}: {
  replies: string[]
  onUse: (reply: string) => void
}) => (
  <section aria-labelledby="specialist-replies-title" className="flex flex-col gap-2">
    <div>
      <h3 id="specialist-replies-title" className="text-ink text-sm font-medium">
        How specialists answered
      </h3>
      <p className="text-mute text-xs">
        Check for customer names or account details before you reuse any of this.
      </p>
    </div>
    <ul className="flex flex-col gap-2">
      {replies.map((reply) => (
        <li
          key={reply}
          className="border-line bg-ice flex flex-col items-start gap-2 rounded-[8px] border p-3"
        >
          <p className="text-ink line-clamp-4 text-sm whitespace-pre-line">{reply}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label={`Use as draft: ${reply.slice(0, 60)}`}
            onClick={() => onUse(reply)}
          >
            Use as draft
          </Button>
        </li>
      ))}
    </ul>
  </section>
)

const SaveActions = ({
  canSave,
  submitting,
  onClose,
}: {
  canSave: boolean
  submitting: boolean
  onClose: () => void
}) => (
  <DialogFooter className="flex-row items-center justify-end gap-2">
    <Button type="button" variant="outline" size="lg" onClick={onClose}>
      Cancel
    </Button>
    <Button type="submit" variant="default" size="lg" disabled={!canSave}>
      {submitting ? <Spinner data-icon="inline-start" /> : null}
      {submitting ? "Saving…" : "Save answer"}
    </Button>
  </DialogFooter>
)

const AnswerForm = ({
  gap,
  isAdmin,
  replies,
  similar,
  submitting,
  error,
  onClose,
  onSubmit,
}: AnswerDialogProps & { gap: GapRecord }) => {
  const [shortcut, setShortcut] = useState(() => suggestShortcut(gap.question))
  const [title, setTitle] = useState(gap.question)
  const [answer, setAnswer] = useState("")
  const [chosen, setChosen] = useState<AnswerKind>("canned")
  // The recommendation is a hint only; fields never swap while staff are typing.
  const recommended: AnswerKind = isAdmin ? recommendedKind(answer) : "canned"
  const kind: AnswerKind = isAdmin ? chosen : "canned"
  const name = kind === "canned" ? shortcut : title
  const canSave = answer.trim() !== "" && name.trim() !== "" && !submitting

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSave) return
    const body = answer.trim()
    onSubmit(
      kind === "canned"
        ? { kind, shortcut: shortcut.trim(), body }
        : { kind, title: title.trim(), body },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-none px-5 py-5">
        <div className="border-line bg-ice rounded-[8px] border p-3">
          <p className="text-mute text-xs font-medium">Visitors asked</p>
          <p className="text-navy heading mt-1 text-sm">{gap.question}</p>
        </div>
        <ClosestEntries similar={similar} />
        {replies.length > 0 ? <SpecialistReplies replies={replies} onUse={setAnswer} /> : null}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="suggested-faq-answer" className="text-ink text-sm font-medium">
            Answer
          </label>
          <Textarea
            id="suggested-faq-answer"
            value={answer}
            maxLength={ANSWER_MAX}
            rows={5}
            onChange={(event) => setAnswer(event.target.value)}
          />
        </div>
        <KindFieldset
          kind={kind}
          recommended={recommended}
          isAdmin={isAdmin}
          onSelect={setChosen}
        />
        <NameField
          kind={kind}
          shortcut={shortcut}
          title={title}
          onShortcut={setShortcut}
          onTitle={setTitle}
        />
        <FieldError className="h-auto">{error || undefined}</FieldError>
      </div>
      <SaveActions canSave={canSave} submitting={submitting} onClose={onClose} />
    </form>
  )
}

export const AnswerDialog = (props: AnswerDialogProps) => (
  <Dialog
    open={props.gap !== null}
    onOpenChange={(open) => {
      if (!open) props.onClose()
    }}
  >
    <DialogContent showCloseButton>
      <DialogHeader>
        <DialogTitle>Answer this question</DialogTitle>
        <DialogDescription>
          Nothing reaches visitors until you save. The assistant never publishes on its own.
        </DialogDescription>
      </DialogHeader>
      {props.gap ? <AnswerForm key={props.gap.id} {...props} gap={props.gap} /> : null}
    </DialogContent>
  </Dialog>
)
