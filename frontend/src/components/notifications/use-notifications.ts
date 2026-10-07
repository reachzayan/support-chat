"use client"

import { useRouter } from "next/navigation"
import { useCallback, useEffect, useRef, useState, type RefObject } from "react"

import { staffRead, staffWrite } from "@/components/admin/staff-api"
import { toast } from "@/components/ui/toast"

import { applyConversationRead, applyRead, mergeFeed } from "./notification-feed"
import { notificationTitle, type NotificationFeed, type NotificationItem } from "./types"

const announceNew = (
  next: NotificationFeed,
  previousId: number | null,
  open: (item: NotificationItem) => Promise<boolean>,
  activeConversation: string | null,
) => {
  if (previousId === null) return null
  const fresh = next.items.filter(
    (item) =>
      item.id > previousId &&
      !item.read_at &&
      (document.hidden || item.conversation_id !== activeConversation),
  )
  if (fresh.length === 0) return null
  const toastId = toast.add({
    type: "message",
    timeout: 6000,
    title:
      fresh.length === 1
        ? notificationTitle[fresh[0].scenario]
        : `${fresh.length} new notifications`,
    description:
      fresh.length === 1 ? fresh[0].site_name : "Open notifications to review your chats.",
    actionProps: {
      children: "View chat",
      onClick: async () => {
        if (await open(fresh[0])) toast.close(toastId)
      },
    },
  })
  return fresh[0]
}

const fetchNotifications = async (cursor?: number): Promise<NotificationFeed> => {
  const response = await staffRead(`/api/notifications${cursor ? `?cursor=${cursor}` : ""}`)
  if (!response.ok) throw new Error("unavailable")
  return response.json()
}

type FeedUpdate = (current: NotificationFeed | null) => NotificationFeed | null

type ReadState = {
  begin: () => boolean
  end: () => void
  commitFeed: (update: FeedUpdate) => void
  setError: (value: boolean) => void
}

const writeRead = async (
  url: string,
  body: object,
  update: FeedUpdate,
  commitFeed: ReadState["commitFeed"],
  setError: ReadState["setError"],
) => {
  try {
    const response = await staffWrite(url, "POST", body)
    if (!response.ok) throw new Error("unavailable")
    commitFeed(update)
    setError(false)
    return true
  } catch {
    setError(true)
    return false
  }
}

const useNotificationReads = ({ begin, end, commitFeed, setError }: ReadState) => {
  const [busy, setBusy] = useState(false)
  const pending = useRef<Promise<boolean>>(Promise.resolve(true))
  const perform = useCallback(
    (url: string, body: object, update: FeedUpdate) => {
      // Preserve reads when the specialist opens another chat during a request.
      const request = pending.current.then(async () => {
        if (!begin()) return false
        setBusy(true)
        const saved = await writeRead(url, body, update, commitFeed, setError)
        end()
        setBusy(false)
        return saved
      })
      pending.current = request
      return request
    },
    [begin, end, commitFeed, setError],
  )
  const markRead = useCallback(
    async (id?: number, through = 0) => {
      if (!id && !through) return false
      return perform(
        id ? `/api/notifications/${id}/read` : "/api/notifications/read-all",
        id ? {} : { through_id: through },
        (current) => applyRead(current, through, id),
      )
    },
    [perform],
  )
  const markConversation = useCallback(
    async (chatId: string, through: number) => {
      if (!through) return false
      return perform(
        `/api/notifications/conversations/${encodeURIComponent(chatId)}/read`,
        { through_id: through },
        (current) => applyConversationRead(current, chatId, through),
      )
    },
    [perform],
  )
  return { busy, markRead, markConversation }
}

const readActive = (
  feed: NotificationFeed | null,
  chatId: string | null,
  mark: (chatId: string, through: number) => Promise<boolean>,
  boundaries: Map<string, number>,
) => {
  if (!chatId || !feed || document.hidden) return
  const through = feed.latest_id ?? feed.items[0]?.id ?? 0
  if (through <= (boundaries.get(chatId) ?? 0)) return
  boundaries.set(chatId, through)
  void mark(chatId, through).then((saved) => {
    if (!saved && boundaries.get(chatId) === through) boundaries.delete(chatId)
    return saved
  })
}

const useActiveConversation = (
  currentFeed: RefObject<NotificationFeed | null>,
  mark: (chatId: string, through: number) => Promise<boolean>,
) => {
  const activeConversation = useRef<string | null>(null)
  const getActive = useCallback(() => activeConversation.current, [])
  const boundaries = useRef(new Map<string, number>())
  const readCurrent = useCallback(() => {
    readActive(currentFeed.current, activeConversation.current, mark, boundaries.current)
  }, [currentFeed, mark])
  const setActiveConversation = useCallback(
    (chatId: string | null) => {
      activeConversation.current = chatId
      readCurrent()
    },
    [readCurrent],
  )
  return { getActive, setActiveConversation, readCurrent }
}

export const useNotifications = (
  enabled: boolean,
  soundEnabled: boolean,
  playTone: (title?: string, body?: string, onOpen?: () => void) => Promise<boolean>,
) => {
  const { push } = useRouter()
  const [feed, setFeed] = useState<NotificationFeed | null>(null)
  const [error, setError] = useState(false)
  const currentFeed = useRef<NotificationFeed | null>(null)
  const revision = useRef(0)
  const latest = useRef<number | null>(null)
  const mutating = useRef(false)
  const commitFeed = useCallback((update: FeedUpdate) => {
    const next = update(currentFeed.current)
    currentFeed.current = next
    setFeed(next)
  }, [])
  const begin = useCallback(() => {
    if (mutating.current) return false
    mutating.current = true
    revision.current += 1
    return true
  }, [])
  const end = useCallback(() => {
    mutating.current = false
  }, [])
  const { busy, markRead, markConversation } = useNotificationReads({
    begin,
    end,
    commitFeed,
    setError,
  })
  const { getActive, setActiveConversation, readCurrent } = useActiveConversation(
    currentFeed,
    markConversation,
  )
  const open = useCallback(
    async (item: NotificationItem) => {
      if (!(await markRead(item.id))) return false
      push(`/admin/inbox?conversation=${encodeURIComponent(item.conversation_id)}`)
      return true
    },
    [markRead, push],
  )
  const acceptNew = useCallback(
    (next: NotificationFeed) => {
      const first = announceNew(next, latest.current, open, getActive())
      if (first && soundEnabled)
        void playTone(notificationTitle[first.scenario], first.site_name, () => {
          void open(first)
        })
      latest.current = Math.max(latest.current ?? 0, next.items[0]?.id ?? 0)
    },
    [open, soundEnabled, playTone, getActive],
  )
  const refresh = useCallback(
    async (cursor?: number) => {
      if (!enabled || mutating.current) return
      const request = ++revision.current
      try {
        const next = await fetchNotifications(cursor)
        if (request !== revision.current) return
        if (!cursor) acceptNew(next)
        commitFeed((current) => mergeFeed(current, next, cursor !== undefined))
        setError(false)
        readCurrent()
      } catch {
        if (request === revision.current) setError(true)
      }
    },
    [enabled, acceptNew, commitFeed, readCurrent],
  )
  useNotificationPolling(enabled, refresh, revision)
  return { feed, error, busy, refresh, markRead, setActiveConversation }
}

const useNotificationPolling = (
  enabled: boolean,
  refresh: () => Promise<void>,
  revision: RefObject<number>,
) => {
  useEffect(() => {
    if (!enabled) return
    const resume = () => {
      void refresh()
    }
    const start = async () => {
      await refresh()
    }
    void start()
    const timer = window.setInterval(resume, 15000)
    window.addEventListener("focus", resume)
    window.addEventListener("online", resume)
    document.addEventListener("visibilitychange", resume)
    return () => {
      revision.current += 1
      window.clearInterval(timer)
      window.removeEventListener("focus", resume)
      window.removeEventListener("online", resume)
      document.removeEventListener("visibilitychange", resume)
    }
  }, [refresh, enabled, revision])
}
