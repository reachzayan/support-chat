"use client"
import { Autocomplete } from "@base-ui/react/autocomplete"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
  PopoverTitle,
  PopoverDescription,
} from "@/components/ui/popover"
/* oxlint-disable react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-function-as-prop -- The prebuilt popover renders the shell button; composition events update the controller. */
import { StateIcon } from "@/components/ui/state-icon"

import { screenLabel, type SearchItem } from "./search-destinations"
import { SearchResultsList } from "./search-results"
import { useSearchController, type SearchController } from "./use-search-controller"
const itemLabel = (item: SearchItem) => item.title
const searchPosition = {
  side: "bottom",
  align: "center",
  sideOffset: 8,
  collisionPadding: 12,
  positionMethod: "fixed",
  collisionAvoidance: { side: "none", align: "shift", fallbackAxisSide: "none" },
} as const

const SearchInput = ({ state }: { state: SearchController }) => {
  const { inputRef, setComposing, composing, query, clear, onOpenChange } = state
  return (
    <div className="border-line flex shrink-0 items-center gap-1 border-b px-3 py-1.5 sm:gap-3 sm:px-4 sm:py-3">
      <StateIcon name="magnifying-glass" className="text-steel hidden size-5 shrink-0 sm:block" />
      <Autocomplete.Input
        ref={inputRef}
        aria-label="Search workspace records"
        onKeyDown={(event) => {
          if (composing || event.nativeEvent.isComposing || event.keyCode === 229) {
            event.preventBaseUIHandler()
            event.stopPropagation()
          }
        }}
        onCompositionStart={() => setComposing(true)}
        onCompositionEnd={() => setComposing(false)}
        placeholder="Search or go to…"
        enterKeyHint="go"
        maxLength={200}
        autoComplete="off"
        spellCheck={false}
        className="text-ink placeholder:text-mute h-11 min-w-0 flex-1 bg-transparent text-base outline-none"
      />
      {query ? (
        <Button
          variant="ghost"
          size="icon"
          className="size-11 shrink-0 sm:size-8"
          aria-label="Clear search"
          onClick={clear}
        >
          <StateIcon name="x-circle" />
        </Button>
      ) : null}
      <Button
        variant="ghost"
        size="icon"
        className="size-11 shrink-0 sm:size-8"
        aria-label="Close search"
        onClick={() => onOpenChange(false)}
      >
        <StateIcon name="x" />
      </Button>
    </div>
  )
}

const SearchPanel = ({ state }: { state: SearchController }) => (
  <PopoverContent
    initialFocus={state.inputRef}
    positionerProps={searchPosition}
    className="flex max-h-[min(var(--available-height),70dvh,42rem)] w-[calc(100vw-1.5rem)] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-2xl p-0 shadow-2xl motion-reduce:transition-none sm:w-(--anchor-width)"
  >
    <PopoverTitle className="sr-only">Search workspace</PopoverTitle>
    <PopoverDescription className="sr-only">
      Search {screenLabel(state.currentScreen)} first, navigate to a view, or find records across
      the workspace. Use arrow keys to select and Enter to open.
    </PopoverDescription>
    <Autocomplete.Root
      items={state.items}
      value={state.query}
      onValueChange={state.setQuery}
      mode="none"
      inline
      open
      autoHighlight="always"
      itemToStringValue={itemLabel}
    >
      <SearchInput state={state} />
      <SearchResultsList state={state} />
      <Autocomplete.Status className="sr-only">
        {state.loading ? "Searching" : `${state.items.length} results available`}
      </Autocomplete.Status>
    </Autocomplete.Root>
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
  </PopoverContent>
)

export const WorkspaceSearch = ({ isAdmin }: { isAdmin: boolean }) => {
  const state = useSearchController(isAdmin)
  return (
    <Popover open={state.open} onOpenChange={state.onOpenChange} modal={false}>
      <PopoverTrigger
        render={<Button variant="ghost" />}
        aria-label="Search workspace"
        className="h-11 w-full min-w-0 justify-start gap-2 rounded-lg border border-white/15 bg-white/5 px-3 text-white/65 hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white sm:h-9"
      >
        <StateIcon name="magnifying-glass" className="size-5 shrink-0" />
        <span className="truncate text-sm">
          <span className="sm:hidden">Search workspace…</span>
          <span className="hidden sm:inline">
            Search {screenLabel(state.currentScreen).toLowerCase()} and workspace…
          </span>
        </span>
        <kbd className="ml-auto hidden shrink-0 rounded border border-white/15 px-1.5 py-0.5 text-[10px] sm:block">
          ⌘ / Ctrl K
        </kbd>
      </PopoverTrigger>
      <SearchPanel state={state} />
    </Popover>
  )
}
