type ParsedAgent = {
  browser: string
  os: string
}

export const parseUserAgent = (userAgent: string | null | undefined): ParsedAgent => {
  if (!userAgent) {
    return { browser: "Unknown", os: "Unknown" }
  }
  const os = userAgent.includes("Macintosh") || userAgent.includes("Mac OS X") ? "macOS" : "Unknown"
  const browser =
    userAgent.includes("Chrome/") && !userAgent.includes("Edg/") ? "Chrome" : "Unknown"
  return { browser, os }
}

export const safeHttpUrl = (raw: string | null | undefined): string | null => {
  if (!raw) {
    return null
  }
  try {
    const parsed = new URL(raw)
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return raw
    }
  } catch {
    return null
  }
  return null
}
