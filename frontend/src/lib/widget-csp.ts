const exactHttpOrigin = (value: string): string | null => {
  try {
    const url = new URL(value)
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null
    }
    if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
      return null
    }
    return url.origin === value ? value : null
  } catch {
    return null
  }
}

export const widgetFrameAncestorsCsp = (origins: readonly string[]): string => {
  const allowed = origins
    .map(exactHttpOrigin)
    .filter((origin): origin is string => origin !== null)
    .filter((origin, index, all) => all.indexOf(origin) === index)
  if (allowed.length === 0) {
    return "frame-ancestors 'none'"
  }
  return `frame-ancestors ${allowed.join(" ")}`
}

const ancestorsFromPayload = (payload: unknown): string[] => {
  if (payload === null || typeof payload !== "object" || !("ancestors" in payload)) {
    return []
  }
  if (!Array.isArray(payload.ancestors)) {
    return []
  }
  return payload.ancestors.filter((item): item is string => typeof item === "string")
}

const ANCESTOR_CACHE_MS = 60_000

type AncestorCacheEntry = {
  ancestors: string[]
  expiresAt: number
}

const ancestorCache = new Map<string, AncestorCacheEntry>()

const ancestorCacheKey = (siteKey: string, publicKey: string, parentOrigin: string) =>
  `${siteKey}\0${publicKey}\0${parentOrigin}`

export const clearWidgetAncestorCache = () => {
  ancestorCache.clear()
}

const rememberAncestors = (cacheKey: string, ancestors: string[], now: number) => {
  ancestorCache.set(cacheKey, { ancestors, expiresAt: now + ANCESTOR_CACHE_MS })
}

const cachedAncestors = (cacheKey: string, now: number) => {
  const cached = ancestorCache.get(cacheKey)
  if (cached === undefined || cached.expiresAt <= now) {
    return null
  }
  return cached.ancestors
}

const requestAncestors = async (
  fetcher: typeof fetch,
  apiOrigin: string,
  serviceSecret: string,
  siteKey: string,
  publicKey: string,
  parentOrigin: string,
  clientIp: string,
): Promise<string[] | null> => {
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-SupportChat-Widget-CSP": serviceSecret,
    }
    if (clientIp) {
      headers["X-SupportChat-Client-IP"] = clientIp
    }
    const response = await fetcher(`${apiOrigin}/api/internal/widget-frame-ancestors`, {
      method: "POST",
      cache: "no-store",
      headers,
      body: JSON.stringify({
        site_key: siteKey,
        public_key: publicKey,
        parent_origin: parentOrigin,
      }),
      signal: AbortSignal.timeout(2_000),
    })
    if (!response.ok) {
      return null
    }
    const ancestors = ancestorsFromPayload(await response.json())
    return ancestors.includes(parentOrigin) ? [parentOrigin] : []
  } catch {
    return null
  }
}

export const fetchWidgetAncestors = async (
  fetcher: typeof fetch,
  apiOrigin: string,
  serviceSecret: string,
  siteKey: string,
  publicKey: string,
  parentOrigin: string,
  clientIp = "",
  now = Date.now(),
): Promise<string[]> => {
  if (!serviceSecret || !siteKey || !publicKey || exactHttpOrigin(parentOrigin) === null) {
    return []
  }
  const cacheKey = ancestorCacheKey(siteKey, publicKey, parentOrigin)
  const hit = cachedAncestors(cacheKey, now)
  if (hit !== null) {
    return hit
  }
  const allowed = await requestAncestors(
    fetcher,
    apiOrigin,
    serviceSecret,
    siteKey,
    publicKey,
    parentOrigin,
    clientIp,
  )
  if (allowed === null) {
    return []
  }
  rememberAncestors(cacheKey, allowed, now)
  return allowed
}
