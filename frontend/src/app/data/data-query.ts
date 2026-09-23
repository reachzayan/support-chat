import { matchesSearchQuery } from "@/lib/search"

import { STATE_LABEL, type ColumnLabel, type SubmissionRow } from "./data-shared"

export type StateFilter = "all" | "prechat" | "bot" | "queued" | "human" | "closed"

export type DataFilters = {
  search: string
  siteId: string | null
  intent: string | null
  state: StateFilter
}

export type SortDirection = "asc" | "desc"

export type DataSort = {
  column: ColumnLabel
  direction: SortDirection
}

export const EMPTY_FILTERS: DataFilters = {
  search: "",
  siteId: null,
  intent: null,
  state: "all",
}

export const STATE_FILTER_OPTIONS = [
  { value: "all", label: "All states" },
  { value: "queued", label: STATE_LABEL.queued },
  { value: "human", label: STATE_LABEL.human },
  { value: "closed", label: STATE_LABEL.closed },
  { value: "bot", label: STATE_LABEL.bot },
  { value: "prechat", label: STATE_LABEL.prechat },
] as const

export const hasActiveFilters = (filters: DataFilters) => {
  if (filters.search.trim().length > 0) {
    return true
  }
  if (filters.siteId) {
    return true
  }
  if (filters.intent) {
    return true
  }
  return filters.state !== "all"
}

export const siteOptionsFromRows = (rows: SubmissionRow[]) => {
  const seen = new Set<string>()
  const options: { id: string; name: string }[] = []
  for (const item of rows) {
    if (seen.has(item.site_id)) {
      continue
    }
    seen.add(item.site_id)
    options.push({ id: item.site_id, name: item.site_name })
  }
  return options
}

export const intentOptionsFromRows = (rows: SubmissionRow[]) => {
  const seen = new Set<string>()
  const options: string[] = []
  for (const item of rows) {
    const intent = item.intent?.trim()
    if (!intent || seen.has(intent)) {
      continue
    }
    seen.add(intent)
    options.push(intent)
  }
  return options.toSorted((left, right) => left.localeCompare(right))
}

export const filterSubmissions = (rows: SubmissionRow[], filters: DataFilters) => {
  return rows.filter((item) => matchesFilters(item, filters))
}

export const sortSubmissions = (rows: SubmissionRow[], sort: DataSort | null) => {
  if (sort === null || !isSortableColumn(sort.column)) {
    return rows
  }
  const getter = SORT_VALUE[sort.column]
  const copied = [...rows]
  copied.sort((left, right) => compareSortValues(getter(left), getter(right), sort.direction))
  return copied
}

export const nextColumnSort = (current: DataSort | null, column: ColumnLabel): DataSort | null => {
  if (!isSortableColumn(column)) {
    return current
  }
  if (current === null || current.column !== column) {
    return { column, direction: "asc" }
  }
  if (current.direction === "asc") {
    return { column, direction: "desc" }
  }
  return null
}

const matchesFilters = (item: SubmissionRow, filters: DataFilters) => {
  if (!matchesSearchQuery(searchValues(item), filters.search)) {
    return false
  }
  if (filters.siteId && item.site_id !== filters.siteId) {
    return false
  }
  if (filters.intent && item.intent !== filters.intent) {
    return false
  }
  if (filters.state !== "all" && item.state !== filters.state) {
    return false
  }
  return true
}

const searchValues = (row: SubmissionRow) => [
  row.visitor.name,
  row.visitor.email,
  row.visitor.phone,
  row.opening_message,
]

const stringValue = (value: string | null | undefined) => {
  const trimmed = value?.trim()
  return trimmed ? trimmed.toLowerCase() : null
}

const timeValue = (value: string | null | undefined) => {
  if (!value) {
    return null
  }
  const ms = Date.parse(value)
  return Number.isNaN(ms) ? null : ms
}

const SORT_VALUE = {
  Name: (row: SubmissionRow) => stringValue(row.visitor.name),
  Email: (row: SubmissionRow) => stringValue(row.visitor.email),
  Inquiry: (row: SubmissionRow) => stringValue(row.inquiry_type),
  Intent: (row: SubmissionRow) => stringValue(row.intent),
  State: (row: SubmissionRow) => stringValue(row.state),
  Attention: (row: SubmissionRow) => (row.attention_needed ? 1 : 0),
  Assigned: (row: SubmissionRow) => stringValue(row.assigned_agent?.display_name),
  "Visitor since": (row: SubmissionRow) => timeValue(row.visitor.created_at),
  "Chat started": (row: SubmissionRow) => timeValue(row.created_at),
  "Last message": (row: SubmissionRow) => timeValue(row.last_message_at),
  Closed: (row: SubmissionRow) => timeValue(row.closed_at),
} as const satisfies Record<string, (row: SubmissionRow) => string | number | null>

export const isSortableColumn = (column: ColumnLabel): column is SortableColumn => {
  return Object.hasOwn(SORT_VALUE, column)
}

type SortableColumn = keyof typeof SORT_VALUE

const compareSortValues = (
  left: string | number | null,
  right: string | number | null,
  direction: SortDirection,
) => {
  if (left === null && right === null) {
    return 0
  }
  if (left === null) {
    return 1
  }
  if (right === null) {
    return -1
  }
  const factor = direction === "asc" ? 1 : -1
  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * factor
  }
  return String(left).localeCompare(String(right)) * factor
}
