"use client"

export const FIELD = "bg-ice"
export const LABEL = "text-mute text-[10px] font-bold tracking-[0.12em] uppercase"
export const BTN_PRIMARY = "font-bold"
export const BTN_SECONDARY = "font-bold"
export const BTN_DANGER = "font-bold"

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
