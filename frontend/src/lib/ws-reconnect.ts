export type ReconnectSchedulerOptions = {
  baseMs?: number
  capMs?: number
  random?: () => number
  schedule?: (fn: () => void, delayMs: number) => number
  clear?: (id: number) => void
  isDisposed?: () => boolean
  isOnline?: () => boolean
  isVisible?: () => boolean
  onReconnect: () => void
}

export const reconnectDelayMs = (
  attempt: number,
  baseMs = 500,
  capMs = 30_000,
  random = Math.random,
) => {
  const ceiling = Math.min(capMs, baseMs * 2 ** attempt)
  return Math.floor(random() * ceiling)
}

export const createReconnectScheduler = (options: ReconnectSchedulerOptions) => {
  let attempt = 0
  let timerId: number | null = null

  const schedule = options.schedule ?? ((fn, delay) => window.setTimeout(fn, delay))
  const clear = options.clear ?? ((id) => window.clearTimeout(id))
  const isOnline = options.isOnline ?? (() => navigator.onLine)
  const isVisible = options.isVisible ?? (() => !document.hidden)
  const isDisposed = options.isDisposed ?? (() => false)

  const canReconnect = () => !isDisposed() && isOnline() && isVisible()

  const cancel = () => {
    if (timerId !== null) {
      clear(timerId)
      timerId = null
    }
  }

  const markAuthenticated = () => {
    attempt = 0
  }

  const handleClose = () => {
    if (!canReconnect()) {
      return
    }
    cancel()
    const delay = reconnectDelayMs(attempt, options.baseMs, options.capMs, options.random)
    attempt += 1
    timerId = schedule(() => {
      timerId = null
      if (!canReconnect()) {
        return
      }
      options.onReconnect()
    }, delay)
  }

  const dispose = () => {
    cancel()
    attempt = 0
  }

  return { handleClose, markAuthenticated, dispose, cancel }
}
