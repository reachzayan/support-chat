"use client"

import { useCallback, useEffect, useMemo } from "react"

import { createMessageTone } from "@/lib/message-tone"
import { hasActivePush, previewSystemSound } from "@/lib/staff-push"
import { preferNativeSound, showSystemNotification } from "@/lib/system-notification"

export type TonePreviewResult = "native" | "audio" | false

export const useMessageTone = (enabled: boolean) => {
  const tone = useMemo(() => createMessageTone(), [])
  useEffect(() => {
    if (!enabled) return
    // Preload on interaction; the explicit test calls play directly in its click.
    document.addEventListener("pointerdown", tone.prepare, { once: true, capture: true })
    document.addEventListener("keydown", tone.prepare, { once: true, capture: true })
    return () => {
      document.removeEventListener("pointerdown", tone.prepare, true)
      document.removeEventListener("keydown", tone.prepare, true)
      tone.stop()
    }
  }, [enabled, tone])
  const play = useCallback(
    async (title = "New chat activity", body = "SupportChat", onOpen?: () => void) => {
      if (!enabled) return false
      if (preferNativeSound()) {
        // The push worker already requests the OS sound for this event.
        if (hasActivePush()) return true
        if (showSystemNotification(title, body, "supportchat-staff", onOpen)) return true
      }
      return tone.play()
    },
    [enabled, tone],
  )
  const preview = useCallback(async (): Promise<TonePreviewResult> => {
    if (preferNativeSound() && (await previewSystemSound())) return "native"
    return (await tone.play()) ? "audio" : false
  }, [tone])
  return { play, preview }
}
