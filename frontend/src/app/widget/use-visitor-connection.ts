"use client"

import { useEffect, useRef } from "react"

import { parseHostToWidget } from "@/lib/postmessage"
import { createVisitorSocket, visitorSocketUrl } from "@/lib/widget-ws"
import { createReconnectScheduler } from "@/lib/ws-reconnect"

import { isTrustedHostFrame, postToParent } from "./host-bridge"
import {
  applyVisitorFrame,
  isAck,
  isErrorFrame,
  isPrechatAccepted,
  type ChatView,
} from "./visitor-session"

export type SocketApi = ReturnType<typeof createVisitorSocket>

type SocketRef = { current: SocketApi | null }
type ViewRef = { current: ChatView }
type Page = { page_url: string; page_title: string; referrer: string }
type SetView = (updater: (current: ChatView) => ChatView) => void
type SchedulerRef = { current: ReturnType<typeof createReconnectScheduler> | null }

const snapshotCursor = (messages: Record<string, unknown>[] | undefined) =>
  Math.max(
    0,
    ...(messages ?? []).map((message) => (typeof message.id === "number" ? message.id : 0)),
  )

export const useVisitorConnection = (
  page: Page,
  setView: SetView,
  setReconnecting: (value: boolean) => void,
  setSending: (value: boolean) => void,
  setLoadingOlder: (value: boolean) => void,
  socketRef: SocketRef,
  viewRef: ViewRef,
) => {
  const disposedRef = useRef(false)
  const schedulerRef = useRef<ReturnType<typeof createReconnectScheduler> | null>(null)

  useEffect(() => {
    disposedRef.current = false
    schedulerRef.current = createReconnectScheduler({
      onReconnect: () => {
        const socket = socketRef.current
        if (socket === null) {
          return
        }
        socket.reconnect()
      },
      isDisposed: () => disposedRef.current,
    })

    const handleResume = () => {
      if (document.hidden || !navigator.onLine) {
        return
      }
      const socket = socketRef.current
      if (socket === null || socket.isOpen()) {
        return
      }
      schedulerRef.current?.handleClose()
    }
    window.addEventListener("online", handleResume)
    document.addEventListener("visibilitychange", handleResume)

    return () => {
      disposedRef.current = true
      schedulerRef.current?.dispose()
      window.removeEventListener("online", handleResume)
      document.removeEventListener("visibilitychange", handleResume)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [socketRef])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      handleBootstrap(
        event,
        setView,
        setReconnecting,
        setSending,
        setLoadingOlder,
        socketRef,
        viewRef,
        schedulerRef,
      )
    }
    window.addEventListener("message", onMessage)
    return () => window.removeEventListener("message", onMessage)
  }, [setReconnecting, setSending, setLoadingOlder, setView, socketRef, viewRef])

  useEffect(() => {
    const socket = socketRef.current
    if (socket === null) {
      return
    }
    socket.sendHello(page.page_url, page.page_title, page.referrer)
  }, [page, socketRef])
}

const handleBootstrap = (
  event: MessageEvent,
  setView: SetView,
  setReconnecting: (value: boolean) => void,
  setSending: (value: boolean) => void,
  setLoadingOlder: (value: boolean) => void,
  socketRef: SocketRef,
  viewRef: ViewRef,
  schedulerRef: SchedulerRef,
) => {
  if (!isTrustedHostFrame(event)) {
    return
  }
  const frame = parseHostToWidget(event.data)
  if (frame?.type !== "host.bootstrap") {
    return
  }
  const existing = socketRef.current
  const bootstrapCursor = Math.max(
    snapshotCursor(frame.conversation?.messages),
    viewRef.current.lastEventId,
  )
  if (existing !== null) {
    existing.setBootstrapToken(frame.bootstrap_token)
    existing.setConversationId(frame.conversation?.id ?? null)
    existing.setBootstrapCursor(bootstrapCursor)
    existing.reconnect()
    return
  }
  socketRef.current = openSocket(
    frame.bootstrap_token,
    bootstrapCursor,
    frame.conversation?.id ?? null,
    event.origin,
    { page_url: frame.page_url, page_title: frame.page_title, referrer: frame.referrer },
    setView,
    setReconnecting,
    setSending,
    setLoadingOlder,
    socketRef,
    viewRef,
    schedulerRef,
  )
}

const openSocket = (
  token: string,
  lastEventId: number,
  conversationId: string | null,
  origin: string,
  page: Page,
  setView: SetView,
  setReconnecting: (value: boolean) => void,
  setSending: (value: boolean) => void,
  setLoadingOlder: (value: boolean) => void,
  socketRef: SocketRef,
  viewRef: ViewRef,
  schedulerRef: SchedulerRef,
) => {
  const socket = createVisitorSocket({
    url: visitorSocketUrl(),
    bootstrapToken: token,
    lastEventId,
    conversationId,
    parentOrigin: origin,
    onFrame: (frame) => {
      schedulerRef.current?.markAuthenticated()
      setReconnecting(false)
      setView((current) => {
        const next = applyVisitorFrame(current, frame)
        viewRef.current = next
        return next
      })
      if (isPrechatAccepted(frame)) {
        postToParent({ type: "widget.activated" }, origin)
      }
      if (isAck(frame) || isErrorFrame(frame)) {
        setSending(false)
      }
      if (
        typeof frame === "object" &&
        frame !== null &&
        "type" in frame &&
        (frame.type === "history_page" || frame.type === "error")
      ) {
        setLoadingOlder(false)
      }
    },
    onClose: (code) => {
      setLoadingOlder(false)
      handleSocketClose(code, origin, socketRef, viewRef, setReconnecting, schedulerRef)
    },
  })
  socket.sendHello(page.page_url, page.page_title, page.referrer)
  return socket
}

const handleSocketClose = (
  code: number,
  origin: string,
  socketRef: SocketRef,
  viewRef: ViewRef,
  setReconnecting: (value: boolean) => void,
  schedulerRef: SchedulerRef,
) => {
  if (code === 4401) {
    postToParent(
      {
        type: "widget.rebootstrap",
        ...(viewRef.current.conversationId
          ? { conversation_id: viewRef.current.conversationId }
          : {}),
      },
      origin,
    )
    return
  }
  if (code === 1000 || code === 4403) {
    return
  }
  setReconnecting(true)
  if (socketRef.current === null) {
    return
  }
  schedulerRef.current?.handleClose()
}
