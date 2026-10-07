"use client"

import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react"

import { usePreferences } from "@/components/preferences-context"
import { syncExistingPush } from "@/lib/staff-push"

import { useMessageTone, type TonePreviewResult } from "./use-message-tone"
import { useNotifications } from "./use-notifications"

type NotificationState = ReturnType<typeof useNotifications> & {
  previewTone: () => Promise<TonePreviewResult>
}
const NotificationsContext = createContext<NotificationState | null>(null)

const useUnreadTitle = (count: number, enabled: boolean) => {
  useEffect(() => {
    if (!enabled) return
    const base = () => document.title.replace(/^\(\d+\)\s+/, "")
    const update = () => {
      const next = count > 0 ? `(${count}) ${base()}` : base()
      if (document.title !== next) document.title = next
    }
    update()
    // Preserve the count when Next updates the page's title during navigation.
    const observer = new MutationObserver(update)
    observer.observe(document.head, { childList: true, subtree: true, characterData: true })
    return () => {
      observer.disconnect()
      document.title = base()
    }
  }, [count, enabled])
}

export const NotificationsProvider = ({
  children,
  enabled = true,
}: {
  children: ReactNode
  enabled?: boolean
}) => {
  const { notificationSound } = usePreferences()
  const tone = useMessageTone(enabled)
  const notifications = useNotifications(enabled, notificationSound, tone.play)
  useUnreadTitle(notifications.feed?.unread_count ?? 0, enabled)
  usePushUpdates(enabled, !notificationSound, notifications.refresh, tone.play)
  const value = useMemo(
    () => ({ ...notifications, previewTone: tone.preview }),
    [notifications, tone.preview],
  )
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}

export const useNotificationState = () => {
  const context = useContext(NotificationsContext)
  if (!context) throw new Error("Notifications require NotificationsProvider.")
  return context
}

// Inbox components also render in isolated stories without the staff shell.
export const useConversationNotifications = (conversationId: string | null) => {
  const context = useContext(NotificationsContext)
  const setActive = context?.setActiveConversation
  useEffect(() => {
    setActive?.(conversationId)
    return () => setActive?.(null)
  }, [conversationId, setActive])
}

export const useUnreadConversations = () =>
  useContext(NotificationsContext)?.feed?.unread_conversations

const usePushUpdates = (
  enabled: boolean,
  silent: boolean,
  refresh: () => Promise<void>,
  playTone: (title?: string, body?: string) => Promise<boolean>,
) => {
  useEffect(() => {
    const worker = navigator.serviceWorker
    if (!enabled || !worker) return
    const controller = new AbortController()
    void syncExistingPush(silent, controller.signal).catch(() => {
      /* Settings offers a visible retry. */
    })
    const receive = (event: MessageEvent) => {
      if (event.data?.type === "supportchat.push") void refresh()
      if (event.data?.type === "supportchat.push.test" && !silent)
        void playTone("SupportChat sound test", "This test uses your device's notification sound.")
      if (event.data?.type === "supportchat.push.expired")
        void syncExistingPush(silent, controller.signal).catch(() => undefined)
    }
    worker.addEventListener("message", receive)
    return () => {
      controller.abort()
      worker.removeEventListener("message", receive)
    }
  }, [enabled, silent, refresh, playTone])
}
