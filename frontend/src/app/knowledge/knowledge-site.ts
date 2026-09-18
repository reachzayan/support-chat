export type KnowledgeSiteOption = {
  id: string
  key: string
  name: string
}

export const selectedSiteValue = (raw: unknown): string | null => {
  if (typeof raw === "string" && raw.length > 0) {
    return raw
  }
  if (raw !== null && typeof raw === "object" && "value" in raw) {
    const value = (raw as { value: unknown }).value
    if (typeof value === "string" && value.length > 0) {
      return value
    }
  }
  return null
}

export const resolveKnowledgeSiteId = (
  sites: KnowledgeSiteOption[],
  selected: string,
  currentId: string,
): string | null => {
  const match = sites.find(
    (site) => site.id === selected || site.key === selected || site.name === selected,
  )
  if (match === undefined) {
    return null
  }
  if (match.id === currentId) {
    return null
  }
  return match.id
}
