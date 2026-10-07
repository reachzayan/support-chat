"use client"

import { useCallback, useEffect, useState, useSyncExternalStore } from "react"

import { usePreferences } from "@/components/preferences-context"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  disablePush,
  enablePush,
  hasActivePush,
  supportsPush,
  syncExistingPush,
  testPush,
} from "@/lib/staff-push"
import { notificationPermission, subscribeNotificationPermission } from "@/lib/system-notification"

import { PushPreview, usePushPreview } from "./push-preview"
import type { Scenario } from "./types"

const subscribeSupport = () => () => {}
const serverSupport = () => true
const serverPermission = () => "checking" as const
const permissionLabels = {
  granted: "Allowed",
  denied: "Blocked",
  default: "Not requested",
  unavailable: "Unavailable",
  checking: "Checking…",
}

const usePushPreference = (siteId?: string, scenario?: Scenario) => {
  const { notificationSound } = usePreferences()
  const [active, setActive] = useState(false)
  const supported = useSyncExternalStore(subscribeSupport, supportsPush, serverSupport)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState(false)
  useEffect(() => {
    let mounted = true
    const controller = new AbortController()
    void syncExistingPush(!notificationSound, controller.signal)
      .then((enabled) => {
        if (mounted) setActive(enabled)
        return enabled
      })
      .catch(() => {
        if (mounted) {
          setError(true)
          setMessage("Could not check push notifications. Try enabling them again.")
        }
      })
    return () => {
      mounted = false
      controller.abort()
    }
  }, [notificationSound])
  useEffect(() => {
    const update = () => setActive(hasActivePush())
    window.addEventListener("supportchat.push-changed", update)
    window.addEventListener("storage", update)
    return () => {
      window.removeEventListener("supportchat.push-changed", update)
      window.removeEventListener("storage", update)
    }
  }, [])
  const toggle = useCallback(async () => {
    setBusy(true)
    setError(false)
    setMessage("")
    try {
      if (active) await disablePush()
      else await enablePush(!notificationSound)
      setActive(!active)
      setMessage(
        active
          ? "Push notifications are off on this device."
          : "Push notifications are enabled on this device.",
      )
    } catch (failure) {
      setError(true)
      setMessage(
        failure instanceof Error
          ? failure.message
          : "Could not update push notifications. Try again.",
      )
    } finally {
      setBusy(false)
    }
  }, [active, notificationSound])
  const preview = useCallback(async () => {
    setBusy(true)
    setError(false)
    try {
      await testPush(siteId && scenario ? { site_id: siteId, scenario } : undefined)
      setMessage(
        "Test notification queued. It will appear shortly, using your device notification settings.",
      )
    } catch (failure) {
      setError(true)
      setMessage(
        failure instanceof Error ? failure.message : "Could not send the test notification.",
      )
    } finally {
      setBusy(false)
    }
  }, [siteId, scenario])
  return { active, supported, busy, message, error, toggle, preview }
}

export const PushPreference = ({ siteId }: { siteId?: string }) => {
  const sample = usePushPreview(siteId)
  const { active, supported, busy, message, error, toggle, preview } = usePushPreference(
    siteId,
    sample.scenario,
  )
  const permission = useSyncExternalStore(
    subscribeNotificationPermission,
    notificationPermission,
    serverPermission,
  )
  return (
    <div className="min-w-0">
      <h3 className="text-navy text-sm font-semibold">Push notifications on this device</h3>
      <Badge aria-live="polite" className="bg-ice text-navy mt-3 tracking-normal normal-case">
        Browser permission: {permissionLabels[permission]}
      </Badge>
      {permission === "denied" ? (
        <p className="text-ember mt-1 text-xs">
          Allow notifications for this website in your browser's site settings.
        </p>
      ) : null}
      <p className="text-mute mt-1 text-xs">
        Receive selected website activity even when SupportChat is closed. Message tone controls sound;
        your device controls volume.
      </p>
      <p className="text-mute mt-1 text-xs">
        Your device's notification settings also control banners and sound.
      </p>
      {!supported ? (
        <p className="text-mute mt-2 text-xs">
          Push is unavailable in this browser. On iPhone or iPad, add SupportChat to your Home Screen
          and open it there.
        </p>
      ) : null}
      {siteId ? <PushPreview state={sample} /> : null}
      <DeviceActions
        active={active}
        supported={supported}
        busy={busy}
        toggle={toggle}
        preview={preview}
        ready={!sample.loading && !sample.error}
      />
      {message ? (
        <p role={error ? "alert" : "status"} className="text-mute mt-3 text-xs">
          {message}
        </p>
      ) : null}
    </div>
  )
}

const DeviceActions = ({
  active,
  supported,
  busy,
  toggle,
  preview,
  ready,
}: Pick<
  ReturnType<typeof usePushPreference>,
  "active" | "supported" | "busy" | "toggle" | "preview"
> & { ready: boolean }) => (
  <div className="mt-3 flex flex-wrap gap-2">
    <Button
      variant={active ? "outline" : "default"}
      className="min-h-11"
      onClick={toggle}
      disabled={busy || !supported}
    >
      {busy ? "Updating…" : active ? "Turn off push" : "Enable push notifications"}
    </Button>
    {active ? (
      <Button variant="outline" className="min-h-11" onClick={preview} disabled={busy || !ready}>
        Send test notification
      </Button>
    ) : null}
  </div>
)
