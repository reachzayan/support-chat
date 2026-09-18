const DEFAULT_PUBLIC_API_ORIGIN = "http://127.0.0.1:8000"

export const resolvePublicApiOrigin = (explicit?: string): string => {
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
