"use client"

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react"

import { parseHostToWidget, type PublicWidgetConfig } from "@/lib/postmessage"

import { applyHostFrame } from "./apply-host-frame"
import { guessParentOrigin, postToParent } from "./host-bridge"
import { useVisitorConnection, type SocketApi } from "./use-visitor-connection"
import { useWidgetActions } from "./use-widget-actions"
import { applyConversationSnapshot, emptyChat, type ChatView } from "./visitor-session"
import { WidgetBody } from "./widget-body"
import { WidgetShell } from "./widget-shell"

const useTransparentDocument = () => {
  useEffect(() => {
    document.documentElement.style.backgroundColor = "transparent"
    document.body.style.backgroundColor = "transparent"
  }, [])
}

const usePaintedSignal = (
  conversation: ChatView["conversation"],
  config: PublicWidgetConfig | null,
  parentRef: RefObject<string>,
  paintedRef: RefObject<boolean>,
) => {
  useLayoutEffect(() => {
    if (paintedRef.current || config === null || conversation === null) {
      return
    }
    paintedRef.current = true
    postToParent({ type: "widget.painted" }, parentRef.current || guessParentOrigin())
  }, [conversation, config, paintedRef, parentRef])
}

const applyHostBootstrap = (
  event: MessageEvent,
  parentRef: RefObject<string>,
  viewRef: RefObject<ChatView>,
  setParentOrigin: (origin: string) => void,
  setConfig: (config: PublicWidgetConfig) => void,
  setPage: (page: { page_url: string; page_title: string; referrer: string }) => void,
  setView: (updater: (current: ChatView) => ChatView) => void,
) => {
  if (event.source !== window.parent) {
    return
  }
  const frame = parseHostToWidget(event.data)
  if (frame === null) {
    return
  }
  applyHostFrame(frame, event.origin, parentRef.current, setParentOrigin, setConfig, setPage)
  if (frame.type !== "host.bootstrap") {
    return
  }
  parentRef.current = event.origin
  const snapshot = frame.conversation
  if (snapshot === undefined) {
    return
  }
  setView((current) => {
    const next = applyConversationSnapshot(current, snapshot)
    viewRef.current = next
    return next
  })
}

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
  const paintedRef = useRef(false)
  useEffect(() => {
    viewRef.current = view
  }, [view])
  useEffect(() => {
    parentRef.current = parentOrigin
  }, [parentOrigin])
  useTransparentDocument()
  const actions = useWidgetActions(socketRef, parentRef, setSending, setPrivacyVisible)

  const handleHostMessage = useCallback(
    (event: MessageEvent) => {
      applyHostBootstrap(event, parentRef, viewRef, setParentOrigin, setConfig, setPage, setView)
    },
    [parentRef],
  )

  useEffect(() => {
    window.addEventListener("message", handleHostMessage)
    postToParent({ type: "widget.ready" }, guessParentOrigin())
    return () => window.removeEventListener("message", handleHostMessage)
  }, [handleHostMessage])

  usePaintedSignal(view.conversation, config, parentRef, paintedRef)

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
