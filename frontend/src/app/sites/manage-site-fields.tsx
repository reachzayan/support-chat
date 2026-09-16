"use client"

import type { ChangeEvent } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

import { ContactInfoField, WebsiteUrlField } from "./add-site-fields"
import { SiteField } from "./sites-form"
import { FIELD } from "./sites-shared"

const ManageSiteOrigins = ({
  site,
  isAdmin,
  originsText,
  onOrigins,
  errors,
  onOriginsBlur,
}: {
  site: SiteRecord
  isAdmin: boolean
  originsText: string
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
  errors: Record<string, string>
  onOriginsBlur: () => void
}) => {
  const errorId = `manage-origins-${site.id}-error`
  return (
    <Field>
      <FieldLabel htmlFor={`manage-origins-${site.id}`}>Approved origins</FieldLabel>
      <Textarea
        id={`manage-origins-${site.id}`}
        value={originsText}
        disabled={!isAdmin}
        onChange={onOrigins}
        className={`${FIELD} font-mono text-xs leading-6`}
        rows={3}
        aria-invalid={errors.origins ? "true" : undefined}
        aria-describedby={errorId}
        onBlur={onOriginsBlur}
      />
      <FieldError id={errorId}>{errors.origins}</FieldError>
    </Field>
  )
}

const ManageSiteCallbackWindow = ({
  site,
  isAdmin,
  windowHours,
  onWindow,
}: {
  site: SiteRecord
  isAdmin: boolean
  windowHours: number
  onWindow: (event: ChangeEvent<HTMLInputElement>) => void
}) => {
  const unit = windowHours === 1 ? "hour" : "hours"
  return (
    <Field>
      <FieldLabel htmlFor={`manage-window-${site.id}`}>Callback window (hours)</FieldLabel>
      <Input
        id={`manage-window-${site.id}`}
        name="callbackWindow"
        autoComplete="off"
        type="number"
        min={1}
        max={168}
        value={windowHours}
        disabled={!isAdmin}
        onChange={onWindow}
        className={FIELD}
      />
      <FieldDescription>
        A specialist will contact you within {windowHours} {unit}.
      </FieldDescription>
    </Field>
  )
}

// oxlint-disable-next-line max-lines-per-function
export const ManageSiteFields = ({
  site,
  isAdmin,
  name,
  greeting,
  privacyUrl,
  websiteUrl,
  originsText,
  contactInfoText,
  windowHours,
  onName,
  onGreeting,
  onPrivacy,
  onWebsiteUrl,
  onOrigins,
  onContactInfo,
  onWindow,
  errors,
  onNameBlur,
  onPrivacyBlur,
  onWebsiteUrlBlur,
  onOriginsBlur,
}: {
  site: SiteRecord
  isAdmin: boolean
  name: string
  greeting: string
  privacyUrl: string
  websiteUrl: string
  originsText: string
  contactInfoText: string
  windowHours: number
  onName: (event: ChangeEvent<HTMLInputElement>) => void
  onGreeting: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onPrivacy: (event: ChangeEvent<HTMLInputElement>) => void
  onWebsiteUrl: (event: ChangeEvent<HTMLInputElement>) => void
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onContactInfo: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onWindow: (event: ChangeEvent<HTMLInputElement>) => void
  errors: Record<string, string>
  onNameBlur: () => void
  onPrivacyBlur: () => void
  onWebsiteUrlBlur: () => void
  onOriginsBlur: () => void
}) => (
  <>
    <ManageSiteIdentity
      site={site}
      isAdmin={isAdmin}
      name={name}
      privacyUrl={privacyUrl}
      onName={onName}
      onPrivacy={onPrivacy}
      errors={errors}
      onNameBlur={onNameBlur}
      onPrivacyBlur={onPrivacyBlur}
    />
    <WebsiteUrlField
      id={`manage-website-url-${site.id}`}
      value={websiteUrl}
      disabled={!isAdmin}
      error={errors.websiteUrl}
      onChange={onWebsiteUrl}
      onBlur={onWebsiteUrlBlur}
    />
    <Field>
      <FieldLabel htmlFor={`manage-greeting-${site.id}`}>Greeting</FieldLabel>
      <Textarea
        id={`manage-greeting-${site.id}`}
        name="greeting"
        autoComplete="off"
        value={greeting}
        disabled={!isAdmin}
        onChange={onGreeting}
        className={`${FIELD} leading-6`}
        rows={3}
      />
    </Field>
    <ManageSiteOrigins
      site={site}
      isAdmin={isAdmin}
      originsText={originsText}
      onOrigins={onOrigins}
      errors={errors}
      onOriginsBlur={onOriginsBlur}
    />
    <ContactInfoField
      id={`manage-contact-info-${site.id}`}
      value={contactInfoText}
      disabled={!isAdmin}
      onChange={onContactInfo}
    />
    <ManageSiteCallbackWindow
      site={site}
      isAdmin={isAdmin}
      windowHours={windowHours}
      onWindow={onWindow}
    />
  </>
)

const ManageSiteIdentity = ({
  site,
  isAdmin,
  name,
  privacyUrl,
  onName,
  onPrivacy,
  errors,
  onNameBlur,
  onPrivacyBlur,
}: {
  site: SiteRecord
  isAdmin: boolean
  name: string
  privacyUrl: string
  onName: (event: ChangeEvent<HTMLInputElement>) => void
  onPrivacy: (event: ChangeEvent<HTMLInputElement>) => void
  errors: Record<string, string>
  onNameBlur: () => void
  onPrivacyBlur: () => void
}) => (
  <div className="grid gap-4 md:grid-cols-2">
    <SiteField
      id={`manage-name-${site.id}`}
      label="Name"
      value={name}
      disabled={!isAdmin}
      onChange={onName}
      error={errors.name}
      onBlur={onNameBlur}
    />
    <SiteField
      id={`manage-privacy-${site.id}`}
      label="Privacy URL"
      value={privacyUrl}
      disabled={!isAdmin}
      onChange={onPrivacy}
      error={errors.privacyUrl}
      onBlur={onPrivacyBlur}
    />
  </div>
)

export const ManageSiteSnippet = ({
  site,
  copyNotice,
  onCopy,
}: {
  site: SiteRecord
  copyNotice: string | null
  onCopy: () => void
}) => (
  <Field>
    <FieldLabel htmlFor={`manage-snippet-${site.id}`}>Embed snippet</FieldLabel>
    <Textarea
      id={`manage-snippet-${site.id}`}
      readOnly
      value={site.snippet}
      className="border-navy-mid bg-navy-deep w-full rounded-lg border p-3 font-mono text-[11px] leading-5 text-white"
      rows={6}
    />
    <FieldDescription>
      Identifies this brand to the widget. Keep the public key in the embed snippet with the site
      key.
    </FieldDescription>
    <button
      type="button"
      onClick={onCopy}
      className="border-line bg-paper text-ink hover:bg-ice focus-visible:ring-steel w-fit cursor-pointer rounded-lg border px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
    >
      Copy snippet
    </button>
    {copyNotice ? <output className="text-steel text-xs">{copyNotice}</output> : null}
  </Field>
)
