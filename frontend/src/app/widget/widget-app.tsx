"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { parseHostToWidget, type PublicWidgetConfig } from "@/lib/postmessage"

import { applyHostFrame } from "./apply-host-frame"
import { guessParentOrigin, postToParent } from "./host-bridge"
import { useVisitorConnection, type SocketApi } from "./use-visitor-connection"
import { useWidgetActions } from "./use-widget-actions"
import { emptyChat, type ChatView } from "./visitor-session"
import { WidgetBody } from "./widget-body"
import { WidgetShell } from "./widget-shell"

export const WidgetApp = () => {
  const [parentOrigin, setParentOrigin] = useState("")
  const [config, setConfig] = useState<PublicWidgetConfig | null>(null)
  const [page, setPage] = useState({ page_url: "", page_title: "", referrer: "" })
  const [view, setView] = useState<ChatView>(emptyChat)
  const [reconnecting, setReconnecting] = useState(false)
  const [sending, setSending] = useState(false)
  const [privacyVisible, setPrivacyVisible] = useState(true)
  const socketRef = useRef<SocketApi | null>(null)
  const viewRef = useRef(view)
  const parentRef = useRef(parentOrigin)
  useEffect(() => {
    viewRef.current = view
  }, [view])
  useEffect(() => {
    parentRef.current = parentOrigin
  }, [parentOrigin])
  const actions = useWidgetActions(socketRef, parentRef, setSending, setPrivacyVisible)

  const handleHostMessage = useCallback(
    (event: MessageEvent) => {
      if (event.source !== window.parent) {
        return
      }
      const frame = parseHostToWidget(event.data)
      if (frame === null) {
        return
      }
      applyHostFrame(frame, event.origin, parentRef.current, setParentOrigin, setConfig, setPage)
    },
    [parentRef],
  )

  useEffect(() => {
    window.addEventListener("message", handleHostMessage)
    postToParent({ type: "widget.ready" }, guessParentOrigin())
    return () => window.removeEventListener("message", handleHostMessage)
  }, [handleHostMessage])

  useVisitorConnection(page, setView, setReconnecting, setSending, socketRef, viewRef)

  if (config === null) {
    return <div className="bg-paper h-dvh" />
  }
  return (
    <WidgetShell
      name={config.name}
      onClose={actions.handleClose}
      onReset={actions.handleReset}
      onResize={actions.handleResize}
    >
      <WidgetBody
        config={config}
        view={view}
        reconnecting={reconnecting}
        sending={sending}
        privacyVisible={privacyVisible}
        onPrechat={actions.handlePrechat}
        onRestart={actions.handleRestart}
        onSend={actions.handleSend}
        onDismissPrivacy={actions.handleDismissPrivacy}
      />
    </WidgetShell>
  )
}
