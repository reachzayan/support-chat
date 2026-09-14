"use client"

import { useCallback } from "react"

import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"

import { RouteSwitch } from "./sites-form"

const siteDescription = (site: SiteRecord) =>
  site.enabled !== false
    ? "Widget and support bot can load on approved origins."
    : "Disabled. Bootstrap fails the same way as an unknown site."

const botDescription = (site: SiteRecord) =>
  site.bot_enabled
    ? "The assistant answers from this brand's knowledge."
    : `We collect the form and promise a callback within ${site.callback_window_hours ?? 24} hours.`

const patchRouting = async (
  site: SiteRecord,
  body: Record<string, unknown>,
  onSaved: (site: SiteRecord) => void,
  onError: (message: string | null) => void,
) => {
  const response = await staffWrite(`/api/sites/${site.id}`, "PATCH", body)
  if (!response.ok) {
    onError("Could not update routing.")
    return
  }
  onError(null)
  onSaved((await response.json()) as SiteRecord)
}

// oxlint-disable-next-line max-lines-per-function
export const ManageSiteRouting = ({
  site,
  isAdmin,
  onSaved,
  onError,
}: {
  site: SiteRecord
  isAdmin: boolean
  onSaved: (site: SiteRecord) => void
  onError: (message: string | null) => void
}) => {
  const handleBot = useCallback(async () => {
    const nextBot = !site.bot_enabled
    const body = nextBot
      ? { bot_enabled: true, human_enabled: site.human_enabled }
      : { bot_enabled: false, human_enabled: false }
    await patchRouting(site, body, onSaved, onError)
  }, [onError, onSaved, site])

  const handleHuman = useCallback(async () => {
    if (!site.bot_enabled) {
      return
    }
    await patchRouting(site, { human_enabled: !site.human_enabled }, onSaved, onError)
  }, [onError, onSaved, site])

  const handleSite = useCallback(async () => {
    await patchRouting(site, { enabled: !(site.enabled !== false) }, onSaved, onError)
  }, [onError, onSaved, site])

  return (
    <div className="grid gap-2">
      <RouteSwitch
        label="Site"
        description={siteDescription(site)}
        checked={site.enabled !== false}
        disabled={!isAdmin}
        ariaDisabled={false}
        onToggle={handleSite}
        accent="steel"
      />
      <RouteSwitch
        label="AI bot"
        description={botDescription(site)}
        checked={site.bot_enabled}
        disabled={!isAdmin}
        ariaDisabled={false}
        onToggle={handleBot}
        accent="steel"
      />
      <RouteSwitch
        label="Human"
        description="Live specialists can join. Requires AI bot."
        checked={site.human_enabled}
        disabled={!isAdmin || !site.bot_enabled}
        ariaDisabled={!site.bot_enabled}
        onToggle={handleHuman}
        accent="ember"
      />
    </div>
  )
}
