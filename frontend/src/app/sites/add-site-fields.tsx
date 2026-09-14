"use client"

import type { ChangeEvent } from "react"

import { Textarea } from "@/components/ui/textarea"

import { Field } from "./sites-form"
import { FIELD, LABEL } from "./sites-shared"

export const AddSiteFields = ({
  name,
  greeting,
  privacyUrl,
  originsText,
  onName,
  onGreeting,
  onPrivacy,
  onOrigins,
  errors,
  onPrivacyBlur,
  onOriginsBlur,
  onNameBlur,
}: {
  name: string
  greeting: string
  privacyUrl: string
  originsText: string
  onName: (event: ChangeEvent<HTMLInputElement>) => void
  onGreeting: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onPrivacy: (event: ChangeEvent<HTMLInputElement>) => void
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
  errors: Record<string, string>
  onPrivacyBlur: () => void
  onOriginsBlur: () => void
  onNameBlur: () => void
}) => (
  <>
    <Field
      id="add-name"
      label="Name"
      value={name}
      disabled={false}
      onChange={onName}
      error={errors.name}
      onBlur={onNameBlur}
    />
    <div>
      <label className={LABEL} htmlFor="add-greeting">
        Greeting
      </label>
      <Textarea
        id="add-greeting"
        name="greeting"
        autoComplete="off"
        value={greeting}
        onChange={onGreeting}
        className={`${FIELD} leading-6`}
        rows={3}
      />
    </div>
    <Field
      id="add-privacy"
      label="Privacy URL"
      value={privacyUrl}
      disabled={false}
      onChange={onPrivacy}
      error={errors.privacyUrl}
      onBlur={onPrivacyBlur}
    />
    <ApprovedOriginsField
      value={originsText}
      onChange={onOrigins}
      error={errors.origins}
      onBlur={onOriginsBlur}
    />
  </>
)

const ApprovedOriginsField = ({
  value,
  onChange,
  error,
  onBlur,
}: {
  value: string
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void
  error?: string
  onBlur: () => void
}) => (
  <div>
    <label className={LABEL} htmlFor="add-origins">
      Approved origins
    </label>
    <Textarea
      id="add-origins"
      name="origins"
      autoComplete="off"
      value={value}
      onChange={onChange}
      className={`${FIELD} font-mono text-xs leading-6`}
      rows={3}
      aria-invalid={error ? "true" : undefined}
      aria-describedby={error ? "add-origins-error" : undefined}
      onBlur={onBlur}
    />
    {error ? (
      <p id="add-origins-error" className="text-ember mt-1 text-xs" role="alert">
        {error}
      </p>
    ) : null}
    <p className="text-mute mt-2 text-xs leading-5">
      One origin per line. Hosts only — no paths, wildcards, or credentials.
    </p>
  </div>
)
