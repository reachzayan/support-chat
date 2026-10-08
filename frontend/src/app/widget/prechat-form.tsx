"use client"

import { useCallback, useState, type FocusEvent, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { FieldError } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { VisitorProfile } from "@/lib/postmessage"
import { emailError, phoneError, requiredError } from "@/lib/validation"

import { CTA_BUTTON } from "./cta-button"
import { openUrlOnHost } from "./host-bridge"

export type PrechatFields = {
  name: string
  email: string
  phone: string
  inquiryType: string
  message: string
}

type PrechatFormProps = {
  visitorProfile?: VisitorProfile
  name: string
  privacyUrl: string
  onSubmit: (fields: PrechatFields) => void
}

const SUBMIT_RESET_MS = 10_000

const PRIVACY =
  "Replies may be AI-generated and incorrect. Do not share Social Security, driver's-license or medical information."

const FIELD =
  "h-11 rounded-[8px] border border-line bg-paper px-3 py-2.5 text-base! font-normal outline-none transition-colors focus-visible:border-steel focus-visible:ring-2 focus-visible:ring-steel"

const focusNamed = (form: HTMLFormElement, name: string) => {
  const field = form.elements.namedItem(name)
  if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
    field.focus()
  }
}

const readFields = (form: HTMLFormElement): PrechatFields => {
  const data = new FormData(form)
  return {
    name: String(data.get("name") ?? "").trim(),
    email: String(data.get("email") ?? ""),
    phone: String(data.get("phone") ?? ""),
    inquiryType: String(data.get("inquiryType") ?? "other"),
    message: String(data.get("message") ?? ""),
  }
}

export const PrechatForm = ({ name, privacyUrl, onSubmit, visitorProfile }: PrechatFormProps) => {
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const displayName = name
    .replace(/\bdemo\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim()
  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const form = event.currentTarget
      const fields = readFields(form)
      const nextErrors = {
        name: requiredError("Full name", fields.name),
        email: emailError(fields.email),
        phone: phoneError(fields.phone),
      }
      const visibleErrors = Object.fromEntries(
        Object.entries(nextErrors).filter((entry): entry is [string, string] => entry[1] !== null),
      )
      setErrors(visibleErrors)
      if (visibleErrors.name) {
        focusNamed(form, "name")
        return
      }
      if (visibleErrors.email) {
        focusNamed(form, "email")
        return
      }
      if (visibleErrors.phone) {
        focusNamed(form, "phone")
        return
      }
      if (submitting) {
        return
      }
      setSubmitting(true)
      // The form unmounts once the chat starts; re-enable if the server never answers.
      window.setTimeout(() => setSubmitting(false), SUBMIT_RESET_MS)
      onSubmit(fields)
    },
    [onSubmit, submitting],
  )
  const handleBlur = useCallback((event: FocusEvent<HTMLInputElement>) => {
    const { name: fieldName, value } = event.currentTarget
    const error =
      fieldName === "name"
        ? requiredError("Full name", value)
        : fieldName === "phone"
          ? phoneError(value)
          : emailError(value)
    setErrors((current) => {
      if (error === null) {
        const next = { ...current }
        delete next[fieldName]
        return next
      }
      return { ...current, [fieldName]: error }
    })
  }, [])
  const handlePrivacy = useCallback(() => {
    openUrlOnHost(privacyUrl)
  }, [privacyUrl])

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="widget-enter flex min-h-0 flex-1 flex-col bg-transparent"
    >
      <PrechatFields
        visitorProfile={visitorProfile}
        displayName={displayName}
        errors={errors}
        onBlur={handleBlur}
        onPrivacy={handlePrivacy}
        submitting={submitting}
      />
    </form>
  )
}

const PrechatIntro = ({ displayName }: { displayName: string }) => (
  <div>
    <p className="text-steel text-[10px] font-semibold tracking-[0.2em] uppercase">
      Start a conversation
    </p>
    {displayName ? <h2 className="text-navy heading mt-1 text-lg">{displayName}</h2> : null}
    <p className="text-mute mt-1 text-xs leading-5">Tell us how we can help.</p>
  </div>
)

const PrivacyBlock = ({ onPrivacy }: { onPrivacy: () => void }) => (
  <>
    <p className="text-mute rounded-[18px] bg-white/70 px-3 py-2 text-xs leading-5 shadow-[0_6px_18px_rgba(13,31,58,0.06)] backdrop-blur-xl">
      {PRIVACY}
    </p>
    <Button
      type="button"
      variant="link"
      size="sm"
      className="text-steel focus-visible:ring-steel min-h-11 w-fit cursor-pointer text-xs font-bold focus-visible:ring-2"
      onClick={onPrivacy}
    >
      Privacy notice
    </Button>
  </>
)

const SubmitBar = ({ submitting }: { submitting: boolean }) => (
  <div className="border-line/60 shrink-0 border-t bg-white/90 px-4 pt-2.5 pb-3 backdrop-blur-xl">
    <Button
      type="submit"
      variant="default"
      size="lg"
      disabled={submitting}
      aria-busy={submitting}
      className={CTA_BUTTON}
    >
      {submitting ? "Starting chat…" : "Start the chat"}
    </Button>
  </div>
)

const PrechatFields = ({
  visitorProfile,
  displayName,
  errors,
  onBlur,
  onPrivacy,
  submitting,
}: {
  submitting: boolean
  visitorProfile?: VisitorProfile
  displayName: string
  errors: Record<string, string>
  onBlur: (event: FocusEvent<HTMLInputElement>) => void
  onPrivacy: () => void
}) => (
  <>
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain px-4 py-3 sm:px-5 sm:py-4">
      <PrechatIntro displayName={displayName} />
      <Field
        label="Full name"
        name="name"
        defaultValue={visitorProfile?.name}
        autoComplete="name"
        inputMode="text"
        required
        error={errors.name}
        onBlur={onBlur}
      />
      <Field
        label="Email"
        name="email"
        defaultValue={visitorProfile?.email}
        type="email"
        inputMode="email"
        autoComplete="email"
        required
        spellCheck={false}
        error={errors.email}
        onBlur={onBlur}
      />
      <Field
        label="Phone"
        name="phone"
        defaultValue={visitorProfile?.phone}
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        error={errors.phone}
        onBlur={onBlur}
      />
      <InquirySelect />
      <label className="text-ink flex flex-col gap-1 text-sm font-medium" htmlFor="prechat-message">
        Message
        <Textarea
          id="prechat-message"
          name="message"
          rows={3}
          maxLength={2000}
          className={`${FIELD} h-auto min-h-[5.5rem]`}
        />
      </label>
      <PrivacyBlock onPrivacy={onPrivacy} />
    </div>
    <SubmitBar submitting={submitting} />
  </>
)

type FieldProps = {
  defaultValue?: string
  label: string
  name: string
  type?: string
  autoComplete: string
  inputMode?: "text" | "email" | "tel"
  required?: boolean
  spellCheck?: boolean
  error?: string
  onBlur?: (event: FocusEvent<HTMLInputElement>) => void
}

const Field = ({
  defaultValue,
  label,
  name,
  type = "text",
  autoComplete,
  inputMode,
  required,
  spellCheck,
  error,
  onBlur,
}: FieldProps) => {
  const errorId = `${name}-error`
  return (
    <div className="text-ink relative flex flex-col gap-1 text-sm font-medium">
      <label htmlFor={name}>{label}</label>
      <Input
        defaultValue={defaultValue}
        id={name}
        type={type}
        name={name}
        autoComplete={autoComplete}
        inputMode={inputMode}
        autoCapitalize={name === "name" ? "words" : "none"}
        required={required}
        spellCheck={spellCheck}
        className={FIELD}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={errorId}
        onBlur={onBlur}
      />
      <FieldError id={errorId} className="absolute inset-x-0 top-full mt-0.5">
        {error}
      </FieldError>
    </div>
  )
}

const INQUIRY_ITEMS = [
  { label: "Sales", value: "sales" },
  { label: "Results timing", value: "results" },
  { label: "Applicant portal", value: "portal" },
  { label: "Compliance", value: "compliance" },
  { label: "Other", value: "other" },
]

const INQUIRY_LABELS = Object.fromEntries(INQUIRY_ITEMS.map((item) => [item.value, item.label]))

const InquirySelect = () => {
  const [value, setValue] = useState("other")
  const handleValueChange = useCallback((next: string | null) => {
    if (typeof next === "string") {
      setValue(next)
    }
  }, [])
  return (
    <div className="text-ink flex flex-col gap-1 text-sm font-medium">
      <label htmlFor="inquiry-type">Inquiry type</label>
      <input type="hidden" name="inquiryType" value={value} />
      <Select value={value} onValueChange={handleValueChange} items={INQUIRY_LABELS}>
        <SelectTrigger id="inquiry-type" className={`${FIELD} w-full data-[size=default]:h-11`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent align="start" alignItemWithTrigger={false}>
          <SelectGroup>
            {INQUIRY_ITEMS.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}
