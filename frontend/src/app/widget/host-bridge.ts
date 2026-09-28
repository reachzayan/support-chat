import type { WidgetToHost } from "@/lib/postmessage"

export const readPinnedParentOrigin = () => {
  try {
    const raw = new URLSearchParams(window.location.search).get("parent_origin")
    if (raw === null || raw === "" || raw === "*") {
      return ""
    }
    return raw
  } catch {
    return ""
  }
}

export const isPinnedParentOrigin = (eventOrigin: string) => {
  const pinned = readPinnedParentOrigin()
  return pinned === "" || eventOrigin === pinned
}

export const isTrustedHostFrame = (event: MessageEvent) => {
  return event.source === window.parent && isPinnedParentOrigin(event.origin)
}

export const guessParentOrigin = () => {
  const pinned = readPinnedParentOrigin()
  if (pinned !== "") {
    return pinned
  }
  const ancestors = window.location.ancestorOrigins
  if (ancestors !== undefined && ancestors.length > 0) {
    return ancestors[0]
  }
  try {
    return document.referrer === "" ? "" : new URL(document.referrer).origin
  } catch {
    return ""
  }
}

export const postToParent = (payload: WidgetToHost, origin: string) => {
  if (origin === "" || origin === "*") {
    return
  }
  window.parent.postMessage(payload, origin)
}

export const openUrlOnHost = (url: string) => {
  postToParent({ type: "widget.open_url", url }, guessParentOrigin())
}
