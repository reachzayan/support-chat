"use client"

import type { ChangeEvent } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"

import { Field } from "./sites-form"
import { FIELD, LABEL } from "./sites-shared"

const ManageSiteOrigins = ({
  site,
  isAdmin,
  originsText,
  onOrigins,
}: {
  site: SiteRecord
  isAdmin: boolean
  originsText: string
  onOrigins: (event: ChangeEvent<HTMLTextAreaElement>) => void
}) => (
  <div>
    <label className={LABEL} htmlFor={`manage-origins-${site.id}`}>
      Approved origins
    </label>
    <textarea
      id={`manage-origins-${site.id}`}
      value={originsText}
      disabled={!isAdmin}
      onChange={onOrigins}
      className={`${FIELD} font-mono text-xs leading-6`}
      rows={3}
    />
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
      <input
        id={`manage-window-${site.id}`}
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
}) => (
  <>
    <div className="grid gap-4 md:grid-cols-2">
      <Field
        id={`manage-name-${site.id}`}
        label="Name"
        value={name}
        disabled={!isAdmin}
        onChange={onName}
      />
      <Field
        id={`manage-privacy-${site.id}`}
        label="Privacy URL"
        value={privacyUrl}
        disabled={!isAdmin}
        onChange={onPrivacy}
      />
    </div>
    <div>
      <label className={LABEL} htmlFor={`manage-greeting-${site.id}`}>
        Greeting
      </label>
      <textarea
        id={`manage-greeting-${site.id}`}
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
    />
    <ManageSiteCallbackWindow
      site={site}
      isAdmin={isAdmin}
      windowHours={windowHours}
      onWindow={onWindow}
    />
  </>
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
    <textarea
      id={`manage-snippet-${site.id}`}
      readOnly
      value={site.snippet}
      className="border-navy-mid bg-navy-deep text-paper mt-1.5 w-full rounded-[8px] border p-3 font-mono text-[11px] leading-5"
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
