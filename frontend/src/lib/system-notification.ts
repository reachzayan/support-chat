export type BrowserNotificationPermission = NotificationPermission | "unavailable" | "checking"
export const notificationPermission = (): BrowserNotificationPermission =>
  globalThis.Notification?.permission ?? "unavailable"

export const preferNativeSound = () => {
  // macOS Chromium does not attach UNNotificationSound to web notifications.
  // The Notifications API exposes no sound-capability query.
  const macChromium =
    /Macintosh|Mac OS X/.test(navigator.userAgent) &&
    /(?:Chrome|Chromium|Edg|OPR)\//.test(navigator.userAgent)
  return notificationPermission() === "granted" && !macChromium
}

export const subscribeNotificationPermission = (update: () => void) => {
  let active = true
  let status: PermissionStatus | undefined
  window.addEventListener("focus", update)
  window.addEventListener("pageshow", update)
  window.addEventListener("supportchat.notification-permission-changed", update)
  document.addEventListener("visibilitychange", update)
  void navigator.permissions
    ?.query({ name: "notifications" })
    .then((value) => {
      if (!active) return undefined
      status = value
      status.addEventListener("change", update)
      update()
      return undefined
    })
    .catch(() => {
      /* Safari refreshes permission on focus instead. */
    })
  return () => {
    active = false
    status?.removeEventListener("change", update)
    window.removeEventListener("focus", update)
    window.removeEventListener("pageshow", update)
    window.removeEventListener("supportchat.notification-permission-changed", update)
    document.removeEventListener("visibilitychange", update)
  }
}
export const requestSystemNotifications = async (): Promise<boolean> => {
  try {
    if (!globalThis.Notification) return false
    if (Notification.permission === "default") {
      await Notification.requestPermission()
      window.dispatchEvent(new Event("supportchat.notification-permission-changed"))
    }
    return Notification.permission === "granted"
  } catch {
    return false
  }
}

let alertSequence = 0
export const showSystemNotification = (
  title: string,
  body: string,
  tag: string,
  onOpen?: () => void,
): boolean => {
  try {
    if (notificationPermission() !== "granted") return false
    const notification = new Notification(title, {
      body,
      tag: `${tag}-${Date.now()}-${++alertSequence}`,
      silent: false,
    })
    notification.addEventListener("click", () => {
      notification.close()
      window.focus()
      onOpen?.()
    })
    return true
  } catch {
    return false
  }
}
