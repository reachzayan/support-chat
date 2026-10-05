import type { InboxMessage } from "./types"

export const parseCitations = (value: unknown): InboxMessage["citations"] => {
  if (!Array.isArray(value)) {
    return undefined
  }
  const items = value.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return []
    }
    const record = item as Record<string, unknown>
    const sourceUrl = typeof record.source_url === "string" ? record.source_url : null
    const sourceTitle = typeof record.source_title === "string" ? record.source_title : null
    if (!sourceUrl && !sourceTitle) {
      return []
    }
    return [{ source_urls: sourceUrl ? [sourceUrl] : null, source_title: sourceTitle }]
  })
  return items.length > 0 ? items : undefined
}
