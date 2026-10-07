"use client"

import { useCallback, useId, useState } from "react"

import { staffWrite } from "@/components/admin/staff-api"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"

import { scenarios, type PushPreferences, type Scenario, type SitePreferences } from "./types"

export type SavePushPreference = (siteId: string, preference: PushPreferences) => void
const defaultPush: PushPreferences = {
  enabled: true,
  scenarios: ["live", "needs_attention", "visitor_message"],
}
const activityItems = scenarios.map((scenario) => ({ value: scenario.id, label: scenario.label }))

const useSitePushPreference = (site: SitePreferences, onSaved: SavePushPreference) => {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)
  const push = site.push ?? defaultPush
  const save = useCallback(
    async (preference: PushPreferences) => {
      setSaving(true)
      setError(false)
      try {
        const response = await staffWrite("/api/notifications/preferences/push", "PUT", {
          site_id: site.site_id,
          ...preference,
        })
        if (!response.ok) throw new Error("unavailable")
        onSaved(site.site_id, preference)
      } catch {
        setError(true)
      } finally {
        setSaving(false)
      }
    },
    [site.site_id, onSaved],
  )
  const toggle = useCallback(
    (enabled: boolean) => {
      void save({ ...push, enabled })
    },
    [push, save],
  )
  const changeTypes = useCallback(
    (values: Scenario[]) => {
      void save({ ...push, scenarios: values })
    },
    [push, save],
  )
  return { push, saving, error, toggle, changeTypes }
}

export const SitePushPreference = ({
  site,
  onSaved,
}: {
  site: SitePreferences
  onSaved: SavePushPreference
}) => {
  const id = useId()
  const { push, saving, error, toggle, changeTypes } = useSitePushPreference(site, onSaved)
  return (
    <div>
      <Separator className="my-5" />
      <Label
        htmlFor={`${id}-enabled`}
        className="flex min-h-11 cursor-pointer items-center justify-between gap-4"
      >
        <span className="text-ink text-sm font-semibold">Push notifications</span>
        <span id={`${id}-label`} className="sr-only">
          Push notifications for {site.site_name}
        </span>
        <Switch
          id={`${id}-enabled`}
          aria-labelledby={`${id}-label`}
          checked={push.enabled}
          disabled={saving}
          onCheckedChange={toggle}
        />
      </Label>
      <p className="text-mute mt-1 text-xs">
        Receive selected activity on your subscribed devices, even when SupportChat is closed.
      </p>
      <Field className="mt-4">
        <FieldLabel
          htmlFor={`${id}-types`}
          className="text-ink text-sm font-semibold tracking-normal normal-case"
        >
          Push activity
        </FieldLabel>
        <Select
          multiple
          value={push.scenarios}
          onValueChange={changeTypes}
          items={activityItems}
          disabled={saving || !push.enabled}
        >
          <SelectTrigger
            id={`${id}-types`}
            aria-label={`Push activity for ${site.site_name}`}
            className="border-line bg-paper text-navy min-h-11 w-full min-w-0 px-3"
          >
            <SelectValue className="min-w-0 truncate" placeholder="Select activity types" />
          </SelectTrigger>
          <SelectContent align="start" alignItemWithTrigger={false}>
            {scenarios.map((scenario) => (
              <SelectItem key={scenario.id} value={scenario.id} className="min-h-11">
                {scenario.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FieldDescription>
          Choose one or more activity types. In-app preferences above are separate.
        </FieldDescription>
        {push.enabled && push.scenarios.length === 0 ? (
          <p className="text-mute text-xs">
            No activity selected. Push notifications are paused for this site.
          </p>
        ) : null}
      </Field>
      {saving ? (
        <output className="text-mute mt-2 block text-xs">Saving push preferences…</output>
      ) : null}
      {error ? (
        <p role="alert" className="text-ember mt-2 text-sm">
          Could not save push preferences. Your previous choices are unchanged. Try again.
        </p>
      ) : null}
    </div>
  )
}
