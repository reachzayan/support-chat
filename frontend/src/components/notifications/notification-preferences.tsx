"use client"

import { useCallback, useEffect, useId, useMemo, useState, type ReactNode } from "react"

import { RetryError } from "@/components/admin/retry-error"
import { staffRead, staffWrite } from "@/components/admin/staff-api"
import { usePreferences } from "@/components/preferences-context"
import { useSearchTarget } from "@/components/search/workspace-route"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
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

import { useNotificationState } from "./notifications-context"
import { PushPreference } from "./push-preference"
import { SitePushPreference, type SavePushPreference } from "./site-push-preference"
import { scenarios, type Scenario, type SitePreferences } from "./types"

type SavePreference = (siteId: string, scenario: Scenario, enabled: boolean) => void
const emptySites: SitePreferences[] = []

const SitePreferenceCard = ({
  site,
  onSaved,
  onPushSaved,
}: {
  site: SitePreferences
  onSaved: SavePreference
  onPushSaved: SavePushPreference
}) => {
  const [saving, setSaving] = useState<Scenario | null>(null)
  const [error, setError] = useState(false)
  const save = useCallback(
    async (scenario: Scenario, inApp: boolean) => {
      setSaving(scenario)
      setError(false)
      try {
        const response = await staffWrite("/api/notifications/preferences", "PUT", {
          site_id: site.site_id,
          scenario,
          in_app: inApp,
        })
        if (!response.ok) throw new Error("unavailable")
        onSaved(site.site_id, scenario, inApp)
      } catch {
        setError(true)
      } finally {
        setSaving(null)
      }
    },
    [site.site_id, onSaved],
  )
  return (
    <fieldset className="min-w-0">
      <legend className="sr-only">{site.site_name}</legend>
      <Separator className="my-5" />
      <h3 className="text-navy text-sm font-semibold">In-app notifications</h3>
      <p className="text-mute mt-1 mb-2 text-xs leading-5">
        Show these updates in your notification feed and unread badges.
      </p>
      <div className="divide-line divide-y">
        {scenarios.map((scenario) => (
          <PreferenceToggle
            key={scenario.id}
            siteName={site.site_name}
            scenario={scenario}
            checked={site.scenarios[scenario.id]}
            disabled={saving !== null}
            onChange={save}
          />
        ))}
      </div>
      {error ? (
        <p role="alert" className="text-ember mt-2 text-sm">
          Could not save. Your previous preference is unchanged. Try again.
        </p>
      ) : null}
      {saving ? <output className="text-mute text-xs">Saving…</output> : null}
      <SitePushPreference site={site} onSaved={onPushSaved} />
    </fieldset>
  )
}

const PreferenceToggle = ({
  siteName,
  scenario,
  checked,
  disabled,
  onChange,
}: {
  siteName: string
  scenario: (typeof scenarios)[number]
  checked: boolean
  disabled: boolean
  onChange: (scenario: Scenario, enabled: boolean) => void
}) => {
  const id = useId()
  const change = useCallback(
    (enabled: boolean) => onChange(scenario.id, enabled),
    [onChange, scenario.id],
  )
  return (
    <Label
      htmlFor={id}
      className="flex min-h-14 cursor-pointer items-center justify-between gap-4 py-3"
    >
      <span>
        <span className="text-ink block text-sm font-semibold">{scenario.label}</span>
        <span id={`${id}-description`} className="text-mute mt-1 block text-xs">
          {scenario.description}
        </span>
      </span>
      <span id={`${id}-label`} className="sr-only">
        {scenario.label} for {siteName}
      </span>
      <Switch
        id={id}
        aria-labelledby={`${id}-label`}
        aria-describedby={`${id}-description`}
        checked={checked}
        disabled={disabled}
        onCheckedChange={change}
        className="shrink-0"
      />
    </Label>
  )
}

type SitePreferencesPickerProps = {
  sites: SitePreferences[]
  onSaved: SavePreference
  onPushSaved: SavePushPreference
  children: ReactNode
}

const SitePreferencesPicker = ({
  sites,
  onSaved,
  onPushSaved,
  children,
}: SitePreferencesPickerProps) => {
  const target = useSearchTarget()
  const [selectedId, setSelectedId] = useState<string | null>(target.site ?? null)
  const id = useId()
  const site = sites.find((item) => item.site_id === selectedId) ?? sites[0]
  const items = useMemo(
    () => sites.map((item) => ({ value: item.site_id, label: item.site_name })),
    [sites],
  )
  return (
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-2 xl:gap-6">
      <section
        aria-labelledby={`${id}-website`}
        className="border-line bg-paper min-w-0 rounded-lg border p-5 sm:p-6"
      >
        <h2 id={`${id}-website`} className="text-navy heading text-base">
          Website activity
        </h2>
        <p className="text-mute mt-2 mb-5 text-sm leading-6">
          Choose a website, then select the chat updates you want to receive.
        </p>
        {children}
        {site ? (
          <>
            <Field>
              <FieldLabel
                htmlFor={id}
                className="text-ink text-sm font-semibold tracking-normal normal-case"
              >
                Website
              </FieldLabel>
              <Select value={site.site_id} onValueChange={setSelectedId} items={items}>
                <SelectTrigger
                  id={id}
                  className="border-line bg-paper text-navy min-h-11 w-full min-w-0 px-3"
                >
                  <SelectValue className="min-w-0 truncate" />
                </SelectTrigger>
                <SelectContent align="start" alignItemWithTrigger={false}>
                  {sites.map((item) => (
                    <SelectItem
                      key={item.site_id}
                      value={item.site_id}
                      className="min-h-11 [&>span]:min-w-0 [&>span]:shrink"
                    >
                      <span className="truncate">{item.site_name}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <SitePreferenceCard
              key={site.site_id}
              site={site}
              onSaved={onSaved}
              onPushSaved={onPushSaved}
            />
          </>
        ) : null}
      </section>
      <section
        aria-labelledby={`${id}-browser`}
        className="border-line bg-paper min-w-0 rounded-lg border p-5 sm:p-6"
      >
        <h2 id={`${id}-browser`} className="text-navy heading text-base">
          This browser
        </h2>
        <MessageTonePreference />
        <Separator className="my-5" />
        <PushPreference siteId={site?.site_id} />
      </section>
    </div>
  )
}

export const NotificationPreferences = () => {
  const [sites, setSites] = useState<SitePreferences[] | null>(null)
  const [error, setError] = useState(false)
  const onSaved = useCallback<SavePreference>((siteId, scenario, enabled) => {
    setSites(
      (current) =>
        current?.map((site) =>
          site.site_id === siteId
            ? { ...site, scenarios: { ...site.scenarios, [scenario]: enabled } }
            : site,
        ) ?? null,
    )
  }, [])
  const onPushSaved = useCallback<SavePushPreference>((siteId, push) => {
    setSites(
      (current) =>
        current?.map((site) => (site.site_id === siteId ? { ...site, push } : site)) ?? null,
    )
  }, [])
  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const response = await staffRead("/api/notifications/preferences")
        if (!response.ok) throw new Error("unavailable")
        const body: { sites: SitePreferences[] } = await response.json()
        if (active) {
          setSites(body.sites)
          setError(false)
        }
      } catch {
        if (active) setError(true)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [])
  const retry = useCallback(async () => {
    try {
      const response = await staffRead("/api/notifications/preferences")
      if (!response.ok) throw new Error("unavailable")
      const body: { sites: SitePreferences[] } = await response.json()
      setSites(body.sites)
      setError(false)
    } catch {
      setError(true)
    }
  }, [])
  return (
    <section id="notifications" className="min-w-0">
      <p className="text-mute mb-5 text-xs">
        Changes save automatically. Website preferences follow your account across devices.
      </p>
      <SitePreferencesPicker
        sites={sites ?? emptySites}
        onSaved={onSaved}
        onPushSaved={onPushSaved}
      >
        {error ? <RetryError text="Could not load preferences." onRetry={retry} /> : null}
        {!sites && !error ? (
          <output className="text-mute block text-sm">Loading preferences…</output>
        ) : null}
        {sites?.length === 0 ? (
          <p className="text-mute text-sm">
            Notification preferences will appear when a site is added.
          </p>
        ) : null}
      </SitePreferencesPicker>
      <p className="text-mute mt-5 text-xs">Email notifications are not available yet.</p>
    </section>
  )
}

const MessageTonePreference = () => {
  const { notificationSound, setNotificationSound } = usePreferences()
  const { previewTone } = useNotificationState()
  const [result, setResult] = useState<"native" | "audio" | "unavailable" | null>(null)
  const [testing, setTesting] = useState(false)
  const id = useId()
  const preview = useCallback(async () => {
    setTesting(true)
    setResult((await previewTone()) || "unavailable")
    setTesting(false)
  }, [previewTone])
  return (
    <div className="mt-5">
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <Label
          htmlFor={id}
          className="flex min-h-11 min-w-0 flex-1 cursor-pointer items-center gap-4"
        >
          <span className="flex-1">
            <span id={`${id}-label`} className="text-ink block text-sm font-semibold">
              Message tone
            </span>
            <span id={`${id}-description`} className="text-mute mt-1 block text-xs">
              Use native sound where supported, with a message tone as a fallback. Volume follows
              your device and browser settings.
            </span>
          </span>
          <Switch
            id={id}
            aria-label="Message tone"
            aria-labelledby={`${id}-label`}
            aria-describedby={`${id}-description`}
            checked={notificationSound}
            onCheckedChange={setNotificationSound}
          />
        </Label>
        <Button variant="outline" className="min-h-11" onClick={preview} disabled={testing}>
          {testing ? "Testing…" : "Test sound"}
        </Button>
      </div>
      {result === "native" ? (
        <output className="text-mute mt-2 block text-xs">
          Native sound test sent. Your device's notification settings control its sound and volume.
        </output>
      ) : null}
      {result === "audio" ? (
        <output className="text-mute mt-2 block text-xs">
          Test sound playing. If you don't hear it, check your device's output and volume and make
          sure this browser tab isn't muted.
        </output>
      ) : null}
      {result === "unavailable" ? (
        <output className="text-mute mt-2 block text-xs">
          Could not play the test sound. Allow sound for this website in your browser settings, then
          try again.
        </output>
      ) : null}
    </div>
  )
}
