export const widgetFrameAncestorsCsp = (origins: readonly string[]): string => {
  const allowed = origins.filter((origin) => origin.length > 0 && !origin.includes("*"))
  if (allowed.length === 0) {
    return "frame-ancestors 'none'"
  }
  return `frame-ancestors ${allowed.join(" ")}`
}

export const parentOriginFromReferer = (referer: string | null): string => {
  if (!referer) {
    return ""
  }
  try {
    const url = new URL(referer)
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return ""
    }
    if (url.username || url.origin.includes("*")) {
      return ""
    }
    return url.origin
  } catch {
    return ""
  }
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
  parent: string,
  fallback: readonly string[],
): Promise<string[]> => {
  if (parent === "" || parent.includes("*")) {
    return []
  }
  try {
    const response = await fetcher(
      `${apiOrigin}/api/public/widget-frame-ancestors?parent=${encodeURIComponent(parent)}`,
    )
    if (!response.ok) {
      return fallback.includes(parent) ? [parent] : []
    }
    if (ancestorsFromPayload(await response.json()).includes(parent)) {
      return [parent]
    }
    return []
  } catch {
    return fallback.includes(parent) ? [parent] : []
  }
}
