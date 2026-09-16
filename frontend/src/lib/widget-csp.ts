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

export const fetchWidgetAncestors = async (
  fetcher: typeof fetch,
  apiOrigin: string,
  serviceSecret: string,
  siteKey: string,
  publicKey: string,
  parentOrigin: string,
  clientIp = "",
): Promise<string[]> => {
  if (!serviceSecret || !siteKey || !publicKey || exactHttpOrigin(parentOrigin) === null) {
    return []
  }
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
      return []
    }
    const ancestors = ancestorsFromPayload(await response.json())
    return ancestors.includes(parentOrigin) ? [parentOrigin] : []
  } catch {
    return []
  }
}
