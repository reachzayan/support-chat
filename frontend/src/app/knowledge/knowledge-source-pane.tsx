import { useMemo, useState } from "react"

import type { KbPageRecord, KbSourceRecord } from "@/components/admin/staff-api"
import { ScrollArea } from "@/components/ui/scroll-area"

import { PaneSearch } from "./knowledge-pane-search"
import { SourceRow } from "./knowledge-source-row"
import type { SourceListProps, SourcePaneProps } from "./knowledge-source-types"

const EMPTY_PAGES: KbPageRecord[] = []

const groupPagesBySource = (pages: KbPageRecord[]) => {
  const grouped: Record<string, KbPageRecord[]> = {}
  for (const page of pages) {
    const bucket = grouped[page.source_id] ?? []
    bucket.push(page)
    grouped[page.source_id] = bucket
  }
  return grouped
}

const sourceMatchesQuery = (
  source: KbSourceRecord,
  sourcePages: KbPageRecord[],
  needle: string,
) => {
  if (!needle) {
    return true
  }
  if (`${source.display_name ?? ""} ${source.start_url}`.toLocaleLowerCase().includes(needle)) {
    return true
  }
  return sourcePages.some((page) =>
    `${page.title} ${page.url}`.toLocaleLowerCase().includes(needle),
  )
}
export const SourcePane = ({
  isAdmin,
  sources,
  pages,
  selectedSourceId,
  selectedPageId,
  onSync,
  onToggle,
  onDelete,
  onSelect,
  onSelectPage,
  onViewChanges,
}: SourcePaneProps) => {
  const [query, setQuery] = useState("")
  const pagesBySource = useMemo(() => groupPagesBySource(pages), [pages])
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return sources.filter((source) =>
      sourceMatchesQuery(source, pagesBySource[source.id] ?? EMPTY_PAGES, needle),
    )
  }, [pagesBySource, query, sources])
  return (
    <section className="border-line bg-paper flex min-h-0 w-full flex-col border-b lg:w-[28rem] lg:shrink-0 lg:border-r lg:border-b-0">
      <div className="flex h-14 items-center justify-between gap-3 px-5">
        <h2 className="text-navy heading text-sm">Sources</h2>
        <span className="text-mute text-xs font-semibold">{sources.length} connected</span>
      </div>
      {sources.length === 0 ? (
        <div className="flex flex-1 items-center justify-center px-6 py-12 text-center">
          <p className="text-ink heading text-sm">
            Add a website or trusted text this site should answer from.
          </p>
        </div>
      ) : (
        <>
          <div className="px-4 pb-3">
            <PaneSearch
              id="knowledge-source-search"
              label="Search sources"
              value={query}
              onQuery={setQuery}
              placeholder="Search sources"
            />
          </div>
          <ScrollArea className="min-h-0 flex-1">
            <SourceList
              sources={filtered}
              pagesBySource={pagesBySource}
              selectedSourceId={selectedSourceId}
              selectedPageId={selectedPageId}
              isAdmin={isAdmin}
              onSelect={onSelect}
              onSync={onSync}
              onToggle={onToggle}
              onDelete={onDelete}
              onSelectPage={onSelectPage}
              onViewChanges={onViewChanges}
            />
          </ScrollArea>
        </>
      )}
    </section>
  )
}

const SourceList = ({
  sources,
  pagesBySource,
  selectedSourceId,
  selectedPageId,
  isAdmin,
  onSelect,
  onSync,
  onToggle,
  onDelete,
  onSelectPage,
  onViewChanges,
}: SourceListProps) => (
  <ul className="px-2 pb-4">
    {sources.map((source) => (
      <SourceRow
        key={source.id}
        source={source}
        pages={pagesBySource[source.id] ?? EMPTY_PAGES}
        selected={source.id === selectedSourceId}
        selectedPageId={selectedPageId}
        isAdmin={isAdmin}
        onSelect={onSelect}
        onSync={onSync}
        onToggle={onToggle}
        onDelete={onDelete}
        onSelectPage={onSelectPage}
        onViewChanges={onViewChanges}
      />
    ))}
  </ul>
)
