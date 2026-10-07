"use client"

import { CheckCheck } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useCallback, useState } from "react"

import { RetryError } from "@/components/admin/retry-error"
import { Button } from "@/components/ui/button"
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle } from "@/components/ui/drawer"
import { StateIcon } from "@/components/ui/state-icon"
import { useIsMobile } from "@/hooks/use-mobile"

import { useNotificationState } from "./notifications-context"
import { notificationTitle, type NotificationItem } from "./types"
import { UnreadBadge } from "./unread-badge"

const NotificationRow = ({
  item,
  busy,
  onOpen,
}: {
  item: NotificationItem
  busy: boolean
  onOpen: (item: NotificationItem) => void
}) => {
  const open = useCallback(() => onOpen(item), [onOpen, item])
  return (
    <li className="border-line border-b">
      <button
        type="button"
        disabled={busy}
        onClick={open}
        className="hover:bg-ice focus-visible:ring-steel flex w-full cursor-pointer gap-3 p-4 text-left focus-visible:ring-2 focus-visible:outline-none disabled:opacity-60"
      >
        <span
          aria-hidden="true"
          className={`mt-1.5 size-2 shrink-0 rounded-full ${item.read_at ? "bg-transparent" : "bg-ember"}`}
        />
        <span className="min-w-0 flex-1">
          <span className={`text-navy block text-sm ${item.read_at ? "font-medium" : "font-bold"}`}>
            {notificationTitle[item.scenario]}
          </span>
          <span className="text-ink mt-1 block text-sm break-words">{item.site_name}</span>
          <time dateTime={item.created_at} className="text-mute mt-1 block text-xs">
            {new Date(item.created_at).toLocaleString()}
          </time>
          {!item.read_at ? <span className="sr-only">Unread</span> : null}
        </span>
      </button>
    </li>
  )
}

export const NotificationBell = () => {
  const mobile = useIsMobile()
  const [open, setOpen] = useState(false)
  const { feed, error, busy, refresh, markRead } = useNotificationState()
  const router = useRouter()
  const show = useCallback(() => {
    setOpen(true)
    void refresh()
  }, [refresh])
  const retry = useCallback(() => {
    void refresh()
  }, [refresh])
  const readAll = useCallback(() => {
    void markRead(undefined, feed?.items[0]?.id)
  }, [markRead, feed])
  const loadMore = useCallback(() => {
    if (feed?.next_cursor) void refresh(feed.next_cursor)
  }, [feed, refresh])
  const close = useCallback(() => setOpen(false), [])
  const openChat = useCallback(
    async (item: NotificationItem) => {
      if (!item.read_at && !(await markRead(item.id))) return
      setOpen(false)
      router.push(`/admin/inbox?conversation=${encodeURIComponent(item.conversation_id)}`)
    },
    [markRead, router],
  )
  const count = feed?.unread_count ?? 0
  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label={feed ? `Notifications, ${count} unread` : "Notifications"}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={show}
        className="group relative size-11 p-0 text-white hover:bg-transparent hover:text-white aria-expanded:bg-transparent aria-expanded:text-white dark:hover:bg-transparent"
      >
        <StateIcon name="bell" className="size-5" />
        <UnreadBadge count={count} className="absolute top-0.5 right-0 ring-2 ring-[#14161b]" />
        {error ? <span className="sr-only">Notifications unavailable</span> : null}
      </Button>
      <Drawer
        open={open}
        onOpenChange={setOpen}
        swipeDirection={mobile ? "down" : "right"}
        showSwipeHandle={mobile}
      >
        <DrawerContent
          className={
            mobile ? "h-[55dvh] w-full max-w-none gap-0 rounded-3xl" : "w-full max-w-md gap-0"
          }
        >
          <DrawerHeader className={mobile ? "min-h-0 pt-0 pb-4" : undefined}>
            <DrawerTitle>Notifications</DrawerTitle>
          </DrawerHeader>
          <NotificationToolbar close={close} readAll={readAll} disabled={busy || count === 0} />
          {error ? (
            <div className="px-4 py-2">
              <RetryError text="Could not update notifications." onRetry={retry} />
            </div>
          ) : null}
          <NotificationHistory
            feed={feed}
            error={error}
            busy={busy}
            openChat={openChat}
            loadMore={loadMore}
          />
        </DrawerContent>
      </Drawer>
    </>
  )
}

const NotificationToolbar = ({
  close,
  readAll,
  disabled,
}: {
  close: () => void
  readAll: () => void
  disabled: boolean
}) => (
  <div className="border-line bg-ice/50 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b px-5 py-2">
    <Link
      href="/admin/notifications"
      onClick={close}
      className="text-steel flex min-h-11 items-center text-sm underline underline-offset-4"
    >
      Preferences
    </Link>
    <Button variant="ghost" onClick={readAll} disabled={disabled} className="min-h-11">
      <CheckCheck aria-hidden="true" className="size-4" /> Mark all read
    </Button>
  </div>
)

const NotificationHistory = ({
  feed,
  error,
  busy,
  openChat,
  loadMore,
}: {
  feed: import("./types").NotificationFeed | null
  error: boolean
  busy: boolean
  openChat: (item: NotificationItem) => void
  loadMore: () => void
}) => (
  <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
    {!feed && !error ? (
      <output className="text-mute block p-6 text-sm">Loading notifications…</output>
    ) : null}
    {feed?.items.length === 0 ? (
      <p className="text-mute p-6 text-sm">
        You’re all caught up. New chat activity will appear here.
      </p>
    ) : null}
    <ul aria-label="Notification history">
      {feed?.items.map((item) => (
        <NotificationRow key={item.id} item={item} busy={busy} onOpen={openChat} />
      ))}
    </ul>
    {feed?.next_cursor ? (
      <Button variant="ghost" onClick={loadMore} className="m-4">
        Load older notifications
      </Button>
    ) : null}
  </div>
)
