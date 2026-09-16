"use client"

export const FIELD = "bg-ice"
export const LABEL = "text-mute text-[10px] font-bold tracking-[0.12em] uppercase"
export const BTN_PRIMARY =
  "micro-interaction bg-ember text-white dark:text-navy-deep hover:bg-ember-mid focus-visible:ring-steel cursor-pointer rounded-[8px] px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
export const BTN_SECONDARY =
  "border-line bg-paper text-ink hover:bg-ice focus-visible:ring-steel cursor-pointer rounded-[8px] border px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"
export const BTN_DANGER =
  "border-ember/30 bg-ember/10 text-ember hover:bg-ember/15 focus-visible:ring-steel cursor-pointer rounded-[8px] border px-3 py-2 text-xs font-bold focus-visible:ring-2 focus-visible:outline-none"

export const COLUMNS = [
  "Name",
  "Site key",
  "Public key",
  "Origins",
  "Routing",
  "Installed",
  "Actions",
] as const
export type ColumnLabel = (typeof COLUMNS)[number]

export const DEFAULT_WIDTHS: Record<ColumnLabel, number> = {
  Name: 20,
  "Site key": 12,
  "Public key": 14,
  Origins: 10,
  Routing: 16,
  Installed: 14,
  Actions: 20,
}

export const WIDTHS_KEY = "supportchat.sites.column-widths.v4"
export const MIN_WIDTH = 8
export const MAX_WIDTH = 48
export const WIDTH_STEP = 2

export const clampWidth = (value: number) => {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(value)))
}

export const readStoredWidths = (): Record<ColumnLabel, number> => {
  if (typeof window === "undefined") {
    return DEFAULT_WIDTHS
  }
  try {
    const raw = window.localStorage.getItem(WIDTHS_KEY)
    if (!raw) {
      return DEFAULT_WIDTHS
    }
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const next = { ...DEFAULT_WIDTHS }
    for (const label of COLUMNS) {
      const value = parsed[label]
      if (typeof value === "number" && Number.isFinite(value)) {
        next[label] = clampWidth(value)
      }
    }
    return next
  } catch {
    return DEFAULT_WIDTHS
  }
}

export type ModalKind = "add" | "manage" | "delete" | null
