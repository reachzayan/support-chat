"use client"

import { useCallback, type ChangeEvent } from "react"

import { type SiteRecord } from "@/components/admin/staff-api"
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

import { EXPORT_COLUMNS, type ColumnLabel } from "./data-shared"

const ALL_SITES = "all"

export const ExportColumnPicker = ({
  columns,
  onToggle,
  onSelectAll,
}: {
  columns: ColumnLabel[]
  onToggle: (column: ColumnLabel, checked: boolean) => void
  onSelectAll: () => void
}) => (
  <fieldset>
    <legend className="text-ink mb-2 text-sm font-medium">Columns</legend>
    <Button type="button" variant="ghost" size="sm" onClick={onSelectAll}>
      {columns.length === EXPORT_COLUMNS.length ? "Clear all" : "Select all"}
    </Button>
    <div className="mt-2 grid grid-cols-2 gap-2">
      {EXPORT_COLUMNS.map((column) => (
        <ExportColumnOption
          key={column}
          column={column}
          checked={columns.includes(column)}
          onToggle={onToggle}
        />
      ))}
    </div>
  </fieldset>
)

const ExportColumnOption = ({
  column,
  checked,
  onToggle,
}: {
  column: ColumnLabel
  checked: boolean
  onToggle: (column: ColumnLabel, checked: boolean) => void
}) => {
  const handleChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => onToggle(column, event.target.checked),
    [column, onToggle],
  )
  return (
    <label htmlFor={`export-column-${column}`} className="text-ink flex items-center gap-2 text-sm">
      <input
        id={`export-column-${column}`}
        type="checkbox"
        checked={checked}
        onChange={handleChange}
        className="border-line text-ember focus-visible:ring-steel size-4 rounded-sm"
      />
      {column}
    </label>
  )
}

export const ExportDateFields = ({
  dateFrom,
  dateTo,
  onDateFrom,
  onDateTo,
}: {
  dateFrom: string
  dateTo: string
  onDateFrom: (value: string) => void
  onDateTo: (value: string) => void
}) => {
  const handleFrom = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => onDateFrom(event.target.value),
    [onDateFrom],
  )
  const handleTo = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => onDateTo(event.target.value),
    [onDateTo],
  )
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="export-from" className="text-ink text-sm font-medium">
          From
        </label>
        <Input
          id="export-from"
          type="date"
          value={dateFrom}
          onChange={handleFrom}
          aria-label="Export from date"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="export-to" className="text-ink text-sm font-medium">
          To
        </label>
        <Input
          id="export-to"
          type="date"
          value={dateTo}
          onChange={handleTo}
          aria-label="Export to date"
        />
      </div>
    </div>
  )
}

export const ExportSiteField = ({
  siteId,
  sites,
  siteItems,
  onSiteId,
}: {
  siteId: string
  sites: SiteRecord[]
  siteItems: Record<string, string>
  onSiteId: (value: string) => void
}) => {
  const handleSite = useCallback(
    (value: unknown) => {
      if (typeof value === "string" && value.length > 0) {
        onSiteId(value)
      }
    },
    [onSiteId],
  )
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="export-site" className="text-ink text-sm font-medium">
        Site
      </label>
      <Select value={siteId} onValueChange={handleSite} items={siteItems}>
        <SelectTrigger id="export-site" aria-label="Export site" className="border-line bg-ice h-8">
          <SelectValue placeholder="All sites" />
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false} align="start">
          <SelectGroup>
            <SelectItem value={ALL_SITES}>All sites</SelectItem>
            {sites.map((site) => (
              <SelectItem key={site.id} value={site.id}>
                {site.name}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}

export { ALL_SITES }
