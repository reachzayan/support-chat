type Notify = () => void

const NAVIGATE_MS = 300

export const watchNavigation = (win: Window, notify: Notify) => {
  let timer = 0
  const debounced = () => {
    win.clearTimeout(timer)
    timer = win.setTimeout(notify, NAVIGATE_MS)
  }
  const history = win.history
  const push = history.pushState.bind(history)
  const replace = history.replaceState.bind(history)
  history.pushState = ((data: unknown, unused: string, url?: string | URL | null) => {
    const result = push(data, unused, url)
    debounced()
    return result
  }) as History["pushState"]
  history.replaceState = ((data: unknown, unused: string, url?: string | URL | null) => {
    const result = replace(data, unused, url)
    debounced()
    return result
  }) as History["replaceState"]
  win.addEventListener("popstate", debounced)
  const navigation = (win as Window & { navigation?: EventTarget }).navigation
  if (navigation !== undefined) {
    navigation.addEventListener("navigate", debounced)
  }
}
