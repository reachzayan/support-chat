"use client"

import { RefreshCw } from "lucide-react"
import { useCallback } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"

import { BTN_SECONDARY } from "./sites-shared"

const STEPS = [
  "Copy the embed snippet.",
  "Paste the snippet before the closing body tag.",
  "Recheck install status after the page is live.",
]

const installLabel = (site: SiteRecord) => {
  if (site.widget_installed === true) {
    return "Installed"
  }
  if (site.widget_installed === false) {
    return "Not installed"
  }
  return "Not checked"
}

const installClass = (site: SiteRecord) => {
  if (site.widget_installed === true) {
    return "bg-steel/10 text-steel"
  }
  if (site.widget_installed === false) {
    return "bg-ember/10 text-ember"
  }
  return "bg-ice text-mute"
}

export const AddSiteInstallPanel = ({
  site,
  checking,
  copyNotice,
  onCopy,
  onCheckInstall,
}: {
  site: SiteRecord
  checking: boolean
  copyNotice: string | null
  onCopy: (snippet: string) => void
  onCheckInstall: () => void
}) => {
  const handleCopy = useCallback(() => {
    onCopy(site.snippet)
  }, [onCopy, site.snippet])
  const handleCheck = useCallback(() => {
    onCheckInstall()
  }, [onCheckInstall])

  return (
    <div className="flex flex-col gap-5">
      <ol className="flex flex-col gap-2">
        {STEPS.map((step, index) => (
          <li key={step} className="flex items-start gap-3">
            <span className="bg-ice text-navy mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md font-mono text-[10px] font-bold">
              {index + 1}
            </span>
            <span className="text-ink text-sm leading-5">{step}</span>
          </li>
        ))}
      </ol>

      <Field>
        <FieldLabel htmlFor={`add-snippet-${site.id}`}>Embed snippet</FieldLabel>
        <Textarea
          id={`add-snippet-${site.id}`}
          readOnly
          value={site.snippet}
          className="border-navy-mid bg-navy-deep min-h-32 w-full rounded-lg border p-3 font-mono text-[11px] leading-5 text-white"
          rows={6}
        />
        <button type="button" onClick={handleCopy} className={`${BTN_SECONDARY} w-fit`}>
          Copy snippet
        </button>
        {copyNotice ? <output className="text-steel text-xs">{copyNotice}</output> : null}
      </Field>

      <Field>
        <p className="text-mute text-[10px] font-bold tracking-[0.12em] uppercase">Install check</p>
        <div
          className="border-line bg-ice flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5"
          aria-label="Widget install status"
        >
          <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${installClass(site)}`}>
            {installLabel(site)}
          </span>
          <button
            type="button"
            onClick={handleCheck}
            disabled={checking}
            aria-label={`Recheck install status for ${site.name}`}
            title="Recheck install status"
            className={`${BTN_SECONDARY} inline-flex items-center gap-1.5`}
          >
            <RefreshCw
              className={`size-3.5 ${checking ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            Recheck
          </button>
        </div>
        <FieldDescription>We look for the public key on the live website.</FieldDescription>
      </Field>
    </div>
  )
}
