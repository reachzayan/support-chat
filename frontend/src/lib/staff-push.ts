import { staffRead, staffWrite } from "@/components/admin/staff-api"
import { requestSystemNotifications, showSystemNotification } from "@/lib/system-notification"

const KEY = "supportchat.push"
const WORKER = "/staff-push-sw.js"
let revision = 0
let activeSubscription: string | null = null

export const supportsPush = () =>
  Boolean(globalThis.Notification && globalThis.PushManager && navigator.serviceWorker)

export const hasActivePush = () => {
  try {
    return Boolean(localStorage.getItem(KEY))
  } catch {
    return Boolean(activeSubscription)
  }
}

const remember = (id: string | null) => {
  activeSubscription = id
  try {
    if (id) localStorage.setItem(KEY, id)
    else localStorage.removeItem(KEY)
  } catch {
    /* The worker still persists its device configuration. */
  }
  window.dispatchEvent(new Event("supportchat.push-changed"))
}

const configureWorker = (
  worker: ServiceWorker,
  config: { subscription_id: string; silent: boolean } | null,
) =>
  new Promise<void>((resolve, reject) => {
    const channel = new MessageChannel()
    const timeout = setTimeout(() => {
      channel.port1.close()
      reject(new Error("Could not configure push on this device. Try again."))
    }, 3000)
    channel.port1.addEventListener(
      "message",
      (event: MessageEvent<{ ok?: boolean }>) => {
        clearTimeout(timeout)
        channel.port1.close()
        if (event.data.ok) resolve()
        else reject(new Error("Could not configure push on this device. Try again."))
      },
      { once: true },
    )
    channel.port1.start()
    worker.postMessage({ type: "supportchat.push.configure", config }, [channel.port2])
  })

const keyBytes = (value: string) => {
  const raw = atob(
    value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - (value.length % 4)) % 4),
  )
  return Uint8Array.from(raw, (char) => char.charCodeAt(0))
}

const registerDevice = async (
  registration: ServiceWorkerRegistration,
  device: PushSubscription,
  silent: boolean,
  isCurrent: () => boolean,
) => {
  if (!isCurrent()) throw new Error("Push setup was cancelled.")
  const response = await staffWrite("/api/notifications/push/subscriptions", "POST", {
    endpoint: device.endpoint,
    keys: device.toJSON().keys,
    silent,
  })
  if (!response.ok) throw new Error("Could not save this push subscription. Try again.")
  const body: { id: string } = await response.json()
  const worker = registration.active ?? (await navigator.serviceWorker.ready).active
  if (!worker) throw new Error("The notification worker is not ready. Try again.")
  if (!isCurrent()) throw new Error("Push setup was cancelled.")
  await configureWorker(worker, { subscription_id: body.id, silent })
  if (!isCurrent()) throw new Error("Push setup was cancelled.")
  remember(body.id)
}

const waitForWorker = async (registration: ServiceWorkerRegistration) => {
  if (registration.active) return registration
  let timeout: ReturnType<typeof setTimeout> | undefined
  try {
    await Promise.race([
      navigator.serviceWorker.ready,
      new Promise((_, reject) => {
        timeout = setTimeout(
          () => reject(new Error("The notification worker did not start. Try again.")),
          15000,
        )
      }),
    ])
    return registration
  } finally {
    clearTimeout(timeout)
  }
}

const requestPermission = async () => {
  if (globalThis.Notification?.permission === "denied")
    throw new Error("Notifications are blocked. Allow them in your browser settings.")
  if (!supportsPush())
    throw new Error(
      "Push notifications are not supported here. On iPhone or iPad, add SupportChat to your Home Screen and open it there.",
    )
  if (Notification.permission !== "granted" && !(await requestSystemNotifications()))
    throw new Error("Notification permission was not granted.")
}

const loadPublicKey = async () => {
  const response = await staffRead("/api/notifications/push/config")
  if (!response.ok) throw new Error("Could not check push configuration. Try again.")
  const config: { configured: boolean; public_key: string | null } = await response.json()
  if (!config.configured || !config.public_key)
    throw new Error("Push notifications have not been configured by your administrator.")
  return config.public_key
}

export const enablePush = async (silent: boolean) => {
  const current = ++revision
  await requestPermission()
  const publicKey = await loadPublicKey()
  if (current !== revision) throw new Error("Push setup was cancelled.")
  const registration = await waitForWorker(
    await navigator.serviceWorker.register(WORKER, { scope: "/" }),
  )
  const existing = await registration.pushManager.getSubscription()
  const device =
    existing ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(publicKey),
    }))
  try {
    if (current !== revision) throw new Error("Push setup was cancelled.")
    await registerDevice(registration, device, silent, () => current === revision)
    if (current !== revision) {
      await disablePush()
      throw new Error("Push setup was cancelled.")
    }
  } catch (error) {
    remember(null)
    if (!existing) await device.unsubscribe()
    throw error
  }
}

export const syncExistingPush = async (silent: boolean, signal?: AbortSignal) => {
  const current = revision
  if (!supportsPush()) return false
  const registration = await navigator.serviceWorker.getRegistration("/")
  const device = await registration?.pushManager.getSubscription()
  if (!registration || !device) {
    if (current === revision && !signal?.aborted) remember(null)
    return false
  }
  await registerDevice(registration, device, silent, () => current === revision && !signal?.aborted)
  return true
}

export const disablePush = async () => {
  revision += 1
  remember(null)
  if (!navigator.serviceWorker) return
  const registration = await navigator.serviceWorker.getRegistration("/")
  if (registration?.active) {
    try {
      await configureWorker(registration.active, null)
    } catch {
      /* Unsubscribe still prevents future deliveries. */
    }
    const notifications = await registration.getNotifications()
    for (const notification of notifications) notification.close()
  }
  const device = await registration?.pushManager.getSubscription()
  if (!device) return
  await device.unsubscribe()
  try {
    await staffWrite("/api/notifications/push/subscriptions", "DELETE", {
      endpoint: device.endpoint,
    })
  } catch {
    /* Expired endpoints are also removed by the delivery worker. */
  }
}

export const testPush = async (selection?: { site_id: string; scenario: string }) => {
  const registration = await navigator.serviceWorker.getRegistration("/")
  const device = await registration?.pushManager.getSubscription()
  if (!device) throw new Error("Enable push notifications on this device first.")
  const response = await staffWrite("/api/notifications/push/test", "POST", {
    endpoint: device.endpoint,
    ...selection,
  })
  if (!response.ok) throw new Error("Could not send the test notification. Try again.")
}

export const previewSystemSound = async (): Promise<boolean> => {
  try {
    if (!(await requestSystemNotifications())) return false
    if (navigator.serviceWorker) {
      const existing = await navigator.serviceWorker.getRegistration("/")
      const registration = await waitForWorker(
        existing ?? (await navigator.serviceWorker.register(WORKER, { scope: "/" })),
      )
      await registration.showNotification("SupportChat sound test", {
        body: "This test uses your device's notification sound and volume.",
        tag: `supportchat-sound-test-${crypto.randomUUID()}`,
        icon: "/icon-watermark.png",
        silent: false,
        data: { url: new URL("/admin/inbox", location.origin).href },
      })
      return true
    }
    return showSystemNotification(
      "SupportChat sound test",
      "This test uses your device's notification sound and volume.",
      "supportchat-sound-test",
    )
  } catch {
    return false
  }
}
