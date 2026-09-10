"use client"

import type { ChangeEvent } from "react"

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
}: {
  name: string
  greeting: string
  privacyUrl: string
  originsText: string
  onName: (event: ChangeEvent<HTMLInputElement>) => void
  onGreeting: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onPrivacy: (event: ChangeEvent<HTMLInputElement>) => void
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
}) => (
  <>
    <Field id="add-name" label="Name" value={name} disabled={false} onChange={onName} />
    <div>
      <label className={LABEL} htmlFor="add-greeting">
        Greeting
      </label>
      <textarea
        id="add-greeting"
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
    />
    <div>
      <label className={LABEL} htmlFor="add-origins">
        Approved origins
      </label>
      <textarea
        id="add-origins"
        value={originsText}
        onChange={onOrigins}
        className={`${FIELD} font-mono text-xs leading-6`}
        rows={3}
      />
      <p className="text-mute mt-2 text-xs leading-5">
        One origin per line. Hosts only — no paths, wildcards, or credentials.
      </p>
    </div>
  </>
)
