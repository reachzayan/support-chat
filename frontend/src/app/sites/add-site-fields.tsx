"use client"

/* oxlint-disable react-perf/jsx-no-new-object-as-prop */

import { Lock } from "lucide-react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import type { ChangeEvent } from "react"

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

import { SiteField } from "./sites-form"
import { FIELD } from "./sites-shared"

const CHIP_TRANSITION = { duration: 0.18, ease: [0.23, 1, 0.32, 1] } as const

// oxlint-disable-next-line max-lines-per-function
export const AddSiteFields = ({
  name,
  greeting,
  privacyUrl,
  websiteUrl,
  lockedOrigin,
  originsText,
  contactInfoText,
  onName,
  onGreeting,
  onPrivacy,
  onWebsiteUrl,
  onOrigins,
  onContactInfo,
  errors,
  onPrivacyBlur,
  onWebsiteUrlBlur,
  onOriginsBlur,
  onNameBlur,
}: {
  name: string
  greeting: string
  privacyUrl: string
  websiteUrl: string
  lockedOrigin: string | null
  originsText: string
  contactInfoText: string
  onName: (event: ChangeEvent<HTMLInputElement>) => void
  onGreeting: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onPrivacy: (event: ChangeEvent<HTMLInputElement>) => void
  onWebsiteUrl: (event: ChangeEvent<HTMLInputElement>) => void
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onContactInfo: (event: ChangeEvent<HTMLTextAreaElement>) => void
  errors: Record<string, string>
  onPrivacyBlur: () => void
  onWebsiteUrlBlur: () => void
  onOriginsBlur: () => void
  onNameBlur: () => void
}) => (
  <>
    <SiteField
      id="add-name"
      label="Name"
      value={name}
      disabled={false}
      onChange={onName}
      error={errors.name}
      onBlur={onNameBlur}
    />
    <WebsiteUrlField
      id="add-website-url"
      value={websiteUrl}
      disabled={false}
      error={errors.websiteUrl}
      onChange={onWebsiteUrl}
      onBlur={onWebsiteUrlBlur}
    />
    <SiteField
      id="add-privacy"
      label="Privacy URL"
      value={privacyUrl}
      disabled={false}
      onChange={onPrivacy}
      error={errors.privacyUrl}
      onBlur={onPrivacyBlur}
    />
    <ApprovedOriginsField
      lockedOrigin={lockedOrigin}
      value={originsText}
      onChange={onOrigins}
      error={errors.origins}
      onBlur={onOriginsBlur}
    />
    <GreetingField value={greeting} disabled={false} onChange={onGreeting} />
    <ContactInfoField
      id="add-contact-info"
      value={contactInfoText}
      disabled={false}
      onChange={onContactInfo}
    />
  </>
)

export const WebsiteUrlField = ({
  id,
  value,
  disabled,
  error,
  onChange,
  onBlur,
}: {
  id: string
  value: string
  disabled: boolean
  error?: string
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
  onBlur: () => void
}) => {
  const errorId = `${id}-error`
  return (
    <Field>
      <FieldLabel htmlFor={id}>Website URL</FieldLabel>
      <Input
        id={id}
        name={id}
        autoComplete="off"
        value={value}
        disabled={disabled}
        onChange={onChange}
        onBlur={onBlur}
        className={FIELD}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={errorId}
      />
      <FieldDescription>
        The live site to crawl for the knowledge base and to check for the widget snippet.
      </FieldDescription>
      <FieldError id={errorId}>{error}</FieldError>
    </Field>
  )
}

const GreetingField = ({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled: boolean
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void
}) => (
  <Field>
    <FieldLabel htmlFor="add-greeting">Greeting</FieldLabel>
    <Textarea
      id="add-greeting"
      name="greeting"
      autoComplete="off"
      value={value}
      disabled={disabled}
      onChange={onChange}
      className={`${FIELD} leading-6`}
      rows={3}
    />
  </Field>
)

export const ContactInfoField = ({
  id,
  value,
  disabled,
  onChange,
}: {
  id: string
  value: string
  disabled: boolean
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void
}) => (
  <Field>
    <FieldLabel htmlFor={id}>Contact info</FieldLabel>
    <Textarea
      id={id}
      name={id}
      autoComplete="off"
      value={value}
      disabled={disabled}
      onChange={onChange}
      className={`${FIELD} font-mono text-xs leading-6`}
      rows={2}
    />
    <FieldDescription>
      One phone number or email per line. The bot shares these when a chat ends or when a visitor
      asks how to reach you.
    </FieldDescription>
  </Field>
)

const ApprovedOriginsField = ({
  lockedOrigin,
  value,
  onChange,
  error,
  onBlur,
}: {
  lockedOrigin: string | null
  value: string
  onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void
  error?: string
  onBlur: () => void
}) => {
  const reducedMotion = useReducedMotion()
  const transition = reducedMotion ? { duration: 0 } : CHIP_TRANSITION
  const errorId = "add-origins-error"

  return (
    <Field>
      <p className="text-mute text-[10px] font-semibold tracking-[0.12em] uppercase">
        Approved origins
      </p>
      <AnimatePresence initial={false}>
        {lockedOrigin ? (
          <motion.div
            key={lockedOrigin}
            initial={{ opacity: 0, y: reducedMotion ? 0 : 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: reducedMotion ? 0 : -4 }}
            transition={transition}
            className="border-line bg-ice flex items-center gap-2 rounded-lg border px-3 py-2"
          >
            <Lock className="text-mute size-3.5 shrink-0" aria-hidden="true" />
            <span className="text-navy min-w-0 truncate font-mono text-xs">{lockedOrigin}</span>
            <span className="text-mute ml-auto shrink-0 text-[10px] font-semibold tracking-[0.12em] uppercase">
              From website
            </span>
          </motion.div>
        ) : (
          <motion.div
            key="origins-hint"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transition}
          >
            <FieldDescription>
              Enter a website URL to add its origin. That origin stays locked to this site.
            </FieldDescription>
          </motion.div>
        )}
      </AnimatePresence>
      <FieldLabel htmlFor="add-origins" className="mt-1">
        Additional origins
      </FieldLabel>
      <Textarea
        id="add-origins"
        name="origins"
        autoComplete="off"
        value={value}
        onChange={onChange}
        className={`${FIELD} font-mono text-xs leading-6`}
        rows={2}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={errorId}
        onBlur={onBlur}
      />
      <FieldError id={errorId}>{error}</FieldError>
      <FieldDescription>
        Optional extra hosts. One origin per line — no paths, wildcards, or credentials.
      </FieldDescription>
    </Field>
  )
}
