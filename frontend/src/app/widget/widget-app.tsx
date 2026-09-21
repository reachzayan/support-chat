"use client"

/* oxlint-disable max-lines-per-function -- this component owns the widget's small view state */

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react"

import {
  parseHostToWidget,
  type ConversationHistoryItem,
  type PublicWidgetConfig,
  type ReturningIdentity,
} from "@/lib/postmessage"

import { applyHostFrame } from "./apply-host-frame"
import { guessParentOrigin, postToParent } from "./host-bridge"
import { ReturningHome } from "./returning-home"
import { useVisitorConnection, type SocketApi } from "./use-visitor-connection"
import { useWidgetActions } from "./use-widget-actions"
import {
  applyConversationSnapshot,
  emptyChat,
  type ChatView,
  type ConversationState,
} from "./visitor-session"
import { WidgetBody } from "./widget-body"
import { WidgetShell } from "./widget-shell"

const useTransparentDocument = () => {
  useEffect(() => {
    document.documentElement.style.backgroundColor = "transparent"
    document.body.style.backgroundColor = "transparent"
  }, [])
}

const usePaintedSignal = (
  ready: boolean,
  config: PublicWidgetConfig | null,
  parentRef: RefObject<string>,
  paintedRef: RefObject<boolean>,
) => {
  useLayoutEffect(() => {
    if (paintedRef.current || config === null || !ready) {
      return
    }
    paintedRef.current = true
    postToParent({ type: "widget.painted" }, parentRef.current || guessParentOrigin())
  }, [ready, config, paintedRef, parentRef])
}

type ReturningView =
  | { mode: "identity"; identity: ReturningIdentity }
  | { mode: "history"; identity: ReturningIdentity; conversations: ConversationHistoryItem[] }
  | null

const shouldKeepClosedView = (
  current: ChatView,
  snapshot: { id?: string; state: ConversationState },
) => {
  if (current.conversation !== "closed") {
    return false
  }
  const isExplicitNewChat =
    snapshot.state === "prechat" &&
    snapshot.id !== undefined &&
    snapshot.id !== current.conversationId
  return !isExplicitNewChat
}

const applyReturningFrame = (
  frame: Extract<
    ReturnType<typeof parseHostToWidget>,
    { type: "host.identity" } | { type: "host.history" }
  >,
  viewRef: RefObject<ChatView>,
  setReturning: (view: ReturningView) => void,
) => {
  if (viewRef.current.conversation === "closed") {
    return
  }
  if (frame.type === "host.identity") {
    setReturning({ mode: "identity", identity: frame.identity })
    return
  }
  setReturning({
    mode: "history",
    identity: frame.identity,
    conversations: frame.conversations,
  })
}

const applyBootstrapConversation = (
  snapshot: {
    id?: string
    state: ConversationState
    assigned_agent: { id: string; display_name: string } | null
    messages: unknown[]
  },
  viewRef: RefObject<ChatView>,
  setView: (updater: (current: ChatView) => ChatView) => void,
) => {
  if (shouldKeepClosedView(viewRef.current, snapshot)) {
    return
  }
  setView(() => {
    const next = applyConversationSnapshot(emptyChat(), snapshot)
    viewRef.current = next
    return next
  })
}

const applyHostBootstrap = (
  event: MessageEvent,
  parentRef: RefObject<string>,
  viewRef: RefObject<ChatView>,
  setParentOrigin: (origin: string) => void,
  setConfig: (config: PublicWidgetConfig) => void,
  setPage: (page: { page_url: string; page_title: string; referrer: string }) => void,
  setView: (updater: (current: ChatView) => ChatView) => void,
  setReturning: (view: ReturningView) => void,
) => {
  if (event.source !== window.parent) {
    return
  }
  const frame = parseHostToWidget(event.data)
  if (frame === null) {
    return
  }
  applyHostFrame(frame, event.origin, parentRef.current, setParentOrigin, setConfig, setPage)
  if (
    frame.type === "host.bootstrap" ||
    frame.type === "host.identity" ||
    frame.type === "host.history"
  ) {
    parentRef.current = event.origin
  }
  if (frame.type === "host.identity" || frame.type === "host.history") {
    applyReturningFrame(frame, viewRef, setReturning)
    return
  }
  if (frame.type !== "host.bootstrap") {
    return
  }
  setReturning(null)
  const snapshot = frame.conversation
  if (snapshot === undefined) {
    return
  }
  applyBootstrapConversation(snapshot, viewRef, setView)
}

export const WidgetApp = () => {
  const [parentOrigin, setParentOrigin] = useState("")
  const [config, setConfig] = useState<PublicWidgetConfig | null>(null)
  const [page, setPage] = useState({ page_url: "", page_title: "", referrer: "" })
  const [view, setView] = useState<ChatView>(emptyChat)
  const [reconnecting, setReconnecting] = useState(false)
  const [sending, setSending] = useState(false)
  const [privacyVisible, setPrivacyVisible] = useState(true)
  const [returning, setReturning] = useState<ReturningView>(null)
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
      applyHostBootstrap(
        event,
        parentRef,
        viewRef,
        setParentOrigin,
        setConfig,
        setPage,
        setView,
        setReturning,
      )
    },
    [parentRef],
  )

  useEffect(() => {
    window.addEventListener("message", handleHostMessage)
    postToParent({ type: "widget.ready" }, guessParentOrigin())
    return () => window.removeEventListener("message", handleHostMessage)
  }, [handleHostMessage])

  usePaintedSignal(returning !== null || view.conversation !== null, config, parentRef, paintedRef)

  useVisitorConnection(page, setView, setReconnecting, setSending, socketRef, viewRef)

  if (config === null) {
    return <div className="bg-paper h-dvh" />
  }
  return (
    <WidgetShell
      name={config.name}
      onClose={actions.handleClose}
      onResetCurrent={actions.handleResetCurrent}
      onDeleteAll={actions.handleDeleteAll}
      onResize={actions.handleResize}
    >
      {returning ? (
        returning.mode === "identity" ? (
          <ReturningHome
            mode="identity"
            identity={returning.identity}
            onShowHistory={actions.handleShowHistory}
            onStartFresh={actions.handleDeleteAll}
          />
        ) : (
          <ReturningHome
            mode="history"
            identity={returning.identity}
            conversations={returning.conversations}
            onOpen={actions.handleOpenConversation}
            onStartFresh={actions.handleResetCurrent}
          />
        )
      ) : (
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
      )}
    </WidgetShell>
  )
}
