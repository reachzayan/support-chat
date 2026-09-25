const DIACRITICS = /[\u0300-\u036f]/g
const COMPACT_SEPARATORS = /[\s#()[\].,+\-_/\\]+/g

export const normalizeSearchText = (value: string) =>
  value.normalize("NFKD").replace(DIACRITICS, "").toLowerCase().replace(/\s+/g, " ").trim()

export const matchesSearchQuery = (
  values: ReadonlyArray<string | null | undefined>,
  query: string,
) => {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery) {
    return true
  }

  const normalizedValues = values.filter(Boolean).map((value) => normalizeSearchText(String(value)))
  const haystack = normalizedValues.join(" ")
  const terms = normalizedQuery.split(" ")
  if (terms.every((term) => haystack.includes(term))) {
    return true
  }

  const compactQuery = normalizedQuery.replace(COMPACT_SEPARATORS, "")
  return (
    compactQuery.length > 0 &&
    normalizedValues.some((value) => value.replace(COMPACT_SEPARATORS, "").includes(compactQuery))
  )
}
