"use client"

import { Volume2, VolumeX } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { parseHostToWidget } from "@/lib/postmessage"

import { guessParentOrigin, isTrustedHostFrame, postToParent } from "./host-bridge"

export const WidgetSoundOption = ({ className }: { className: string }) => {
  const [enabled, setEnabled] = useState(true)
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (!isTrustedHostFrame(event)) return
      const frame = parseHostToWidget(event.data)
      if (frame?.type === "host.sound") setEnabled(frame.enabled)
    }
    window.addEventListener("message", receive)
    return () => window.removeEventListener("message", receive)
  }, [])
  const toggle = useCallback(() => {
    postToParent({ type: "widget.sound", enabled: !enabled }, guessParentOrigin())
    setEnabled(!enabled)
  }, [enabled])
  const Icon = enabled ? Volume2 : VolumeX
  return (
    <Button
      type="button"
      variant="ghost"
      role="menuitemcheckbox"
      aria-checked={enabled}
      className={className}
      onClick={toggle}
    >
      <Icon aria-hidden="true" className="size-4" /> Message sound
    </Button>
  )
}
