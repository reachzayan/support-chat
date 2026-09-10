const MAX_URL = 2048
const MAX_TITLE = 200

export const originFromHref = (href: string): string => {
  try {
    const url = new URL(href)
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return ""
    }
    return url.origin
  } catch {
    return ""
  }
}

export const sanitizePageUrl = (raw: string): string => {
  const clipped = raw.length > MAX_URL ? raw.slice(0, MAX_URL) : raw
  try {
    const url = new URL(clipped)
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return ""
    }
    return `${url.origin}${url.pathname}`
  } catch {
    return ""
  }
}

export const sanitizeTitle = (raw: string): string => raw.slice(0, MAX_TITLE)

export const originFromScript = (script: HTMLScriptElement | null): string => {
  if (script === null || script.src === "") {
    return ""
  }
  return originFromHref(script.src)
}
