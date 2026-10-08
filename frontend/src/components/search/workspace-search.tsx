"use client"
import { Autocomplete } from "@base-ui/react/autocomplete"
import { cn } from "cn"

import { Button } from "@/components/ui/button"
/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Search input and control events update the controller. */
import { StateIcon } from "@/components/ui/state-icon"

import { screenLabel, type SearchItem } from "./search-destinations"
import { SearchResultsList } from "./search-results"
import {
  useSearchController,
  useSearchDismiss,
  type SearchController,
} from "./use-search-controller"
const itemLabel = (item: SearchItem) => item.title

const SearchInput = ({ state }: { state: SearchController }) => {
  const { inputRef, setComposing, composing, query, clear, onOpenChange } = state
  return (
    <Autocomplete.InputGroup
      className={cn(
        "flex h-11 w-full min-w-0 items-center gap-2 pr-1 pl-3 sm:h-9",
        state.open
          ? "text-ink"
          : "focus-within:ring-steel rounded-lg border border-white/15 bg-white/5 text-white/65 focus-within:border-white/35 focus-within:bg-white/10 focus-within:text-white focus-within:ring-1",
      )}
    >
      <StateIcon name="magnifying-glass" className="size-5 shrink-0" />
      <Autocomplete.Input
        ref={inputRef}
        aria-label="Search workspace records"
        name="workspace-search"
        onKeyDown={(event) => {
          if (composing || event.nativeEvent.isComposing || event.keyCode === 229) {
            event.preventBaseUIHandler()
            event.stopPropagation()
          }
        }}
        onCompositionStart={() => setComposing(true)}
        onCompositionEnd={() => setComposing(false)}
        placeholder={`Search ${screenLabel(state.currentScreen).toLowerCase()} and workspace…`}
        enterKeyHint="go"
        maxLength={200}
        autoComplete="off"
        spellCheck={false}
        className={cn(
          "h-full min-w-0 flex-1 bg-transparent text-base outline-none sm:text-sm",
          state.open ? "text-ink placeholder:text-mute" : "text-white placeholder:text-white/65",
        )}
      />
      {query ? (
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "size-11 shrink-0 sm:size-7",
            state.open
              ? "text-mute hover:bg-ice hover:text-ink"
              : "text-white/65 hover:bg-white/10 hover:text-white",
          )}
          aria-label="Clear search"
          onClick={clear}
        >
          <StateIcon name="x-circle" />
        </Button>
      ) : null}
      {state.open ? (
        <Button
          variant="ghost"
          size="icon"
          className="text-mute hover:bg-ice hover:text-ink size-11 shrink-0 sm:size-7"
          aria-label="Close search"
          onClick={() => {
            onOpenChange(false)
            inputRef.current?.focus()
          }}
        >
          <StateIcon name="x" />
        </Button>
      ) : (
        <kbd className="mr-2 hidden shrink-0 rounded border border-white/15 px-1.5 py-0.5 text-[10px] sm:block">
          ⌘ / Ctrl K
        </kbd>
      )}
    </Autocomplete.InputGroup>
  )
}

const SearchPanel = ({ state }: { state: SearchController }) => (
  <div className="bg-paper text-ink flex max-h-[min(70dvh,36rem,calc(100dvh-var(--workspace-toolbar-height,3.5rem)-1rem))] min-h-0 flex-col overflow-hidden">
    <SearchResultsList state={state} />
    <Autocomplete.Status className="sr-only">
      {state.loading ? "Searching" : `${state.items.length} results available`}
    </Autocomplete.Status>
    {state.failed ? (
      <div
        role="alert"
        className="border-line text-mute flex shrink-0 items-center justify-between gap-3 border-t px-5 py-3 text-sm"
      >
        <span>Navigation still works. Retry to search records.</span>
        <Button variant="outline" size="sm" onClick={state.retrySearch}>
          Retry
        </Button>
      </div>
    ) : null}
    <div className="border-line text-mute hidden shrink-0 justify-between gap-2 border-t px-5 py-2.5 text-[11px] sm:flex">
      <span>
        ↑ ↓ Select <span className="mx-2">↵ Open</span>
      </span>
      <span>
        {state.groups.some((group) => group.items.length === 12)
          ? "Top 12 per section · Refine to find more"
          : "Esc to close"}
      </span>
    </div>
  </div>
)

export const WorkspaceSearch = ({ isAdmin }: { isAdmin: boolean }) => {
  const state = useSearchController(isAdmin)
  const containerRef = useSearchDismiss(state.open, state.onOpenChange, state.inputRef)
  return (
    <search
      ref={containerRef}
      aria-label="Workspace"
      className="relative z-30 h-11 w-full min-w-0 sm:h-9"
    >
      <Autocomplete.Root
        items={state.items}
        value={state.query}
        onValueChange={state.setQuery}
        open={state.open}
        onOpenChange={state.onOpenChange}
        mode="none"
        modal={false}
        inline={state.open}
        openOnInputClick
        autoHighlight="always"
        itemToStringValue={itemLabel}
      >
        <div
          className={cn(
            "absolute inset-x-0 top-0 rounded-lg",
            state.open &&
              "border-line bg-paper focus-within:border-steel/60 overflow-hidden border shadow-[0_12px_28px_rgba(13,31,58,0.14)]",
          )}
        >
          <SearchInput state={state} />
          {state.open ? <SearchPanel state={state} /> : null}
        </div>
      </Autocomplete.Root>
    </search>
  )
}
