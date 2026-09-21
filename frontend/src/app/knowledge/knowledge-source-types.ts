import type { KbPageRecord, KbSourceRecord } from "@/components/admin/staff-api"

export type SourcePaneProps = {
  isAdmin: boolean
  sources: KbSourceRecord[]
  pages: KbPageRecord[]
  selectedSourceId: string | null
  selectedPageId: string | null
  onSync: (source: KbSourceRecord) => void
  onToggle: (source: KbSourceRecord) => void
  onDelete: (source: KbSourceRecord) => void
  onSelect: (source: KbSourceRecord) => void
  onSelectPage: (page: KbPageRecord) => void
  onViewChanges: (source: KbSourceRecord) => void
}

export type SourceListProps = Omit<SourcePaneProps, "pages"> & {
  pagesBySource: Record<string, KbPageRecord[]>
}

export type SourceRowProps = Omit<SourcePaneProps, "sources" | "selectedSourceId"> & {
  source: KbSourceRecord
  selected: boolean
}
