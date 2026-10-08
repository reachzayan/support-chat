import * as React from "react"

const MOBILE_BREAKPOINT = 768

export function useIsMobile(breakpoint = MOBILE_BREAKPOINT) {
  const subscribe = React.useCallback(
    (onStoreChange: () => void) => {
      if (typeof window.matchMedia !== "function") {
        return () => {}
      }
      const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)
      mql.addEventListener("change", onStoreChange)
      return () => mql.removeEventListener("change", onStoreChange)
    },
    [breakpoint],
  )
  const getSnapshot = React.useCallback(() => window.innerWidth < breakpoint, [breakpoint])
  const getServerSnapshot = React.useCallback(() => false, [])

  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
