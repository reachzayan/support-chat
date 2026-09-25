const DEFAULT_PUBLIC_API_ORIGIN = "http://127.0.0.1:8000"

export const resolvePublicApiOrigin = (explicit?: string): string => {
  // Production serves each surface's socket from its own edge hostname.
  // A build-time API origin cannot represent both staff and widget hosts.
  if (process.env.NODE_ENV === "production" && typeof window !== "undefined") {
    return window.location.origin
  }
  const fromArg = explicit?.trim()
  if (fromArg) {
    return fromArg
  }
  const fromEnv = process.env.NEXT_PUBLIC_API_ORIGIN?.trim()
  if (fromEnv) {
    return fromEnv
  }
  return DEFAULT_PUBLIC_API_ORIGIN
}
