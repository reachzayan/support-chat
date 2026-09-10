"use client"

import { useKnowledgeCatalog } from "./knowledge-catalog"
import { useKnowledgeDiff } from "./knowledge-diff"

export const useKnowledgeState = (isAdmin: boolean) => {
  const catalog = useKnowledgeCatalog(isAdmin)
  const diff = useKnowledgeDiff(catalog.setSources)
  return { ...catalog, ...diff }
}
