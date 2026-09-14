"use client"

import type { ChangeEvent } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

import { Field } from "./sites-form"
import { FIELD, LABEL } from "./sites-shared"

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
}) => (
  <div>
    <label className={LABEL} htmlFor={`manage-origins-${site.id}`}>
      Approved origins
    </label>
    <Textarea
      id={`manage-origins-${site.id}`}
      value={originsText}
      disabled={!isAdmin}
      onChange={onOrigins}
      className={`${FIELD} font-mono text-xs leading-6`}
      rows={3}
      aria-invalid={errors.origins ? "true" : undefined}
      aria-describedby={errors.origins ? `manage-origins-${site.id}-error` : undefined}
      onBlur={onOriginsBlur}
    />
    {errors.origins ? (
      <p id={`manage-origins-${site.id}-error`} className="text-ember mt-1 text-xs" role="alert">
        {errors.origins}
      </p>
    ) : null}
    {site.origins_missing_from_frame_ancestors ? (
      <p className="border-ember/20 bg-ember/10 text-ember mt-2 rounded-[8px] border px-3 py-2.5 text-xs leading-5">
        This origin is missing from the widget frame-ancestors header.
      </p>
    ) : null}
  </div>
)

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
    <div>
      <label className={LABEL} htmlFor={`manage-window-${site.id}`}>
        Callback window (hours)
      </label>
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
      <p className="text-mute mt-2 text-xs leading-5">
        A specialist will contact you within {windowHours} {unit}.
      </p>
    </div>
  )
}

export const ManageSiteFields = ({
  site,
  isAdmin,
  name,
  greeting,
  privacyUrl,
  originsText,
  windowHours,
  onName,
  onGreeting,
  onPrivacy,
  onOrigins,
  onWindow,
  errors,
  onNameBlur,
  onPrivacyBlur,
  onOriginsBlur,
}: {
  site: SiteRecord
  isAdmin: boolean
  name: string
  greeting: string
  privacyUrl: string
  originsText: string
  windowHours: number
  onName: (event: ChangeEvent<HTMLInputElement>) => void
  onGreeting: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onPrivacy: (event: ChangeEvent<HTMLInputElement>) => void
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
  onWindow: (event: ChangeEvent<HTMLInputElement>) => void
  errors: Record<string, string>
  onNameBlur: () => void
  onPrivacyBlur: () => void
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
    <div>
      <label className={LABEL} htmlFor={`manage-greeting-${site.id}`}>
        Greeting
      </label>
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
    </div>
    <ManageSiteOrigins
      site={site}
      isAdmin={isAdmin}
      originsText={originsText}
      onOrigins={onOrigins}
      errors={errors}
      onOriginsBlur={onOriginsBlur}
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
    <Field
      id={`manage-name-${site.id}`}
      label="Name"
      value={name}
      disabled={!isAdmin}
      onChange={onName}
      error={errors.name}
      onBlur={onNameBlur}
    />
    <Field
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
  <div>
    <label className={LABEL} htmlFor={`manage-snippet-${site.id}`}>
      Embed snippet
    </label>
    <Textarea
      id={`manage-snippet-${site.id}`}
      readOnly
      value={site.snippet}
      className="border-navy-mid bg-navy-deep mt-1.5 w-full rounded-[8px] border p-3 font-mono text-[11px] leading-5 text-white"
      rows={6}
    />
    <p className="text-mute mt-2 text-xs leading-5">
      Identifies this brand to the widget. Keep the public key in the embed snippet with the site
      key.
    </p>
    <button
      type="button"
      onClick={onCopy}
      className="border-line bg-paper text-ink hover:bg-ice focus-visible:ring-steel mt-3 cursor-pointer rounded-[8px] border px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
    >
      Copy snippet
    </button>
    {copyNotice ? <output className="text-steel mt-2 block text-xs">{copyNotice}</output> : null}
  </div>
)
