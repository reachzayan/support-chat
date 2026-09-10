import type { WidgetToHost } from "@/lib/postmessage"

export const guessParentOrigin = () => {
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
