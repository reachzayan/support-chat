"use client"

import { useCallback, useMemo, type ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import {
  EMPTY_FILTERS,
  hasActiveFilters,
  intentOptionsFromRows,
  siteOptionsFromRows,
  STATE_FILTER_OPTIONS,
  type DataFilters,
  type StateFilter,
} from "./data-query"
import type { SubmissionRow } from "./data-shared"

const ALL = "all"
const STATE_OPTIONS = STATE_FILTER_OPTIONS.map((option) => ({ ...option }))
const STATE_ITEMS = Object.fromEntries(STATE_OPTIONS.map((option) => [option.value, option.label]))

export const DataFilterBar = ({
  rows,
  filters,
  onFilters,
}: {
  rows: SubmissionRow[]
  filters: DataFilters
  onFilters: (next: DataFilters) => void
}) => {
  const sites = useMemo(() => siteOptionsFromRows(rows), [rows])
  const intents = useMemo(() => intentOptionsFromRows(rows), [rows])
  const siteOptions = useMemo(
    () => [
      { value: ALL, label: "All sites" },
      ...sites.map((site) => ({ value: site.id, label: site.name })),
    ],
    [sites],
  )
  const intentOptions = useMemo(
    () => [
      { value: ALL, label: "All intents" },
      ...intents.map((intent) => ({ value: intent, label: labelIntent(intent) })),
    ],
    [intents],
  )
  const { handleSearch, handleSite, handleIntent, handleState, handleClear } =
    useDataFilterHandlers(filters, onFilters)

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="search"
        autoComplete="off"
        spellCheck={false}
        value={filters.search}
        onChange={handleSearch}
        aria-label="Search submissions"
        placeholder="Search name, email, phone, or message"
        className="border-line bg-ice h-8 min-w-48 flex-1"
      />
      <DataFilterSelect
        label="Site"
        value={filters.siteId ?? ALL}
        options={siteOptions}
        onValueChange={handleSite}
      />
      <DataFilterSelect
        label="Intent"
        value={filters.intent ?? ALL}
        options={intentOptions}
        onValueChange={handleIntent}
      />
      <DataFilterSelect
        label="State"
        value={filters.state}
        options={STATE_OPTIONS}
        items={STATE_ITEMS}
        onValueChange={handleState}
        wide
      />
      {hasActiveFilters(filters) ? (
        <Button type="button" variant="ghost" size="sm" onClick={handleClear}>
          Clear
        </Button>
      ) : null}
    </div>
  )
}

const useDataFilterHandlers = (filters: DataFilters, onFilters: (next: DataFilters) => void) => {
  const handleSearch = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      onFilters({ ...filters, search: event.target.value })
    },
    [filters, onFilters],
  )
  const handleSite = useCallback(
    (value: unknown) => {
      const selected = selectedString(value)
      if (selected === null) {
        return
      }
      onFilters({ ...filters, siteId: selected === ALL ? null : selected })
    },
    [filters, onFilters],
  )
  const handleIntent = useCallback(
    (value: unknown) => {
      const selected = selectedString(value)
      if (selected === null) {
        return
      }
      onFilters({ ...filters, intent: selected === ALL ? null : selected })
    },
    [filters, onFilters],
  )
  const handleState = useCallback(
    (value: unknown) => {
      const selected = selectedString(value)
      if (selected === null || !isStateFilter(selected)) {
        return
      }
      onFilters({ ...filters, state: selected })
    },
    [filters, onFilters],
  )
  const handleClear = useCallback(() => onFilters(EMPTY_FILTERS), [onFilters])

  return { handleSearch, handleSite, handleIntent, handleState, handleClear }
}

const DataFilterSelect = ({
  label,
  value,
  options,
  items,
  onValueChange,
  wide = false,
}: {
  label: string
  value: string
  options: ReadonlyArray<{ value: string; label: string }>
  items?: Record<string, string>
  onValueChange: (value: unknown) => void
  wide?: boolean
}) => {
  const itemsByValue = useMemo(
    () => items ?? Object.fromEntries(options.map((option) => [option.value, option.label])),
    [items, options],
  )
  return (
    <Select value={value} onValueChange={onValueChange} items={itemsByValue}>
      <SelectTrigger
        aria-label={label}
        className={`border-line bg-ice h-8 ${wide ? "min-w-44" : "min-w-40"}`}
      >
        <SelectValue placeholder={options[0]?.label} />
      </SelectTrigger>
      <SelectContent alignItemWithTrigger={false} align="start">
        <SelectGroup>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

const labelIntent = (intent: string) => {
  return intent.slice(0, 1).toUpperCase() + intent.slice(1)
}

const isStateFilter = (value: string): value is StateFilter => {
  return STATE_FILTER_OPTIONS.some((option) => option.value === value)
}

const selectedString = (raw: unknown): string | null => {
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
