"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"

import { useSitesColumnWidths } from "./sites-column-widths"
import { BTN_SECONDARY, COLUMNS, LABEL, type ColumnLabel } from "./sites-shared"

type ResizeHandlers = {
  onResizeStart: (label: ColumnLabel, event: React.PointerEvent<HTMLButtonElement>) => void
  onResizeKeyDown: (label: ColumnLabel, event: React.KeyboardEvent<HTMLButtonElement>) => void
  onResizeReset: (label: ColumnLabel) => void
}

const SitesColumnHeader = ({
  label,
  onResizeStart,
  onResizeKeyDown,
  onResizeReset,
}: {
  label: ColumnLabel
} & ResizeHandlers) => {
  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => onResizeStart(label, event),
    [label, onResizeStart],
  )
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>) => onResizeKeyDown(label, event),
    [label, onResizeKeyDown],
  )
  const handleReset = useCallback(() => onResizeReset(label), [label, onResizeReset])

  return (
    <th
      scope="col"
      className={`${LABEL} border-line relative border-r px-3 py-2.5 last:border-r-0 ${
        label === "Actions" ? "text-right" : ""
      }`}
    >
      <span className="pr-3">{label}</span>
      <button
        type="button"
        aria-label={`Resize ${label} column`}
        title="Drag to resize. Arrow keys adjust. Double-click resets."
        onPointerDown={handlePointerDown}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleReset}
        className="focus-visible:ring-steel absolute top-0 right-0 z-10 h-full w-3 cursor-col-resize touch-none border-0 bg-transparent p-0 focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="bg-line hover:bg-steel focus-visible:bg-steel absolute top-1.5 right-0 bottom-1.5 w-px" />
      </button>
    </th>
  )
}

const SiteRow = ({ site, onManage }: { site: SiteRecord; onManage: (siteId: string) => void }) => {
  const [copied, setCopied] = useState(false)
  const publicPreview = `${site.public_key.slice(0, 6)}…${site.public_key.slice(-4)}`
  const originLabel = site.origins.length === 1 ? "1 origin" : `${site.origins.length} origins`
  const handleManage = useCallback(() => onManage(site.id), [onManage, site.id])
  const siteOn = site.enabled !== false

  useEffect(() => {
    if (!copied) {
      return
    }
    const timer = window.setTimeout(() => setCopied(false), 1000)
    return () => window.clearTimeout(timer)
  }, [copied])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(site.snippet)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }, [site.snippet])

  return (
    <tr className="border-line hover:bg-ice/60 border-b last:border-b-0">
      <td className="text-navy truncate px-3 py-2.5 text-sm font-bold">{site.name}</td>
      <td className="text-mute truncate px-3 py-2.5 font-mono text-xs">{site.key}</td>
      <td className="text-mute truncate px-3 py-2.5 font-mono text-xs" title={site.public_key}>
        {publicPreview}
      </td>
      <td className="text-mute truncate px-3 py-2.5 text-xs">{originLabel}</td>
      <td className="px-3 py-2.5" aria-label="Routing status">
        <div className="flex flex-wrap gap-1">
          <span className="bg-ice text-navy rounded-[6px] px-1.5 py-0.5 text-[10px] font-bold">
            {siteOn ? "Site on" : "Site off"}
          </span>
          <span className="bg-ice text-navy rounded-[6px] px-1.5 py-0.5 text-[10px] font-bold">
            {site.bot_enabled ? "Bot on" : "Bot off"}
          </span>
          <span className="bg-ice text-navy rounded-[6px] px-1.5 py-0.5 text-[10px] font-bold">
            {site.human_enabled ? "Human on" : "Human off"}
          </span>
        </div>
      </td>
      <td className="px-3 py-2.5">
        <div className="flex flex-nowrap items-center justify-end gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            aria-label={copied ? "Copied" : "Copy snippet"}
            className={`${BTN_SECONDARY} min-w-[6.75rem] shrink-0`}
          >
            {copied ? "Copied" : "Copy snippet"}
          </button>
          <button type="button" onClick={handleManage} className={`${BTN_SECONDARY} shrink-0`}>
            Manage
          </button>
        </div>
      </td>
    </tr>
  )
}

export const SitesTable = ({
  sites,
  onManage,
}: {
  sites: SiteRecord[]
  onManage: (siteId: string) => void
}) => {
  const { widths, total, handleResizeStart, handleResizeKeyDown, handleResizeReset } =
    useSitesColumnWidths()
  const tableStyle = useMemo(() => ({ minWidth: `${total * 12}px` }), [total])
  const colStyles = useMemo(
    () =>
      COLUMNS.map((label) => ({
        key: label,
        style: { width: `${(widths[label] / total) * 100}%` },
      })),
    [total, widths],
  )

  return (
    <div className="min-w-0 overflow-x-auto">
      <table
        className="w-full table-fixed border-collapse text-left"
        aria-label="Sites"
        style={tableStyle}
      >
        <colgroup>
          {colStyles.map((col) => (
            <col key={col.key} style={col.style} />
          ))}
        </colgroup>
        <thead className="bg-ice-2 border-line border-b">
          <tr>
            {COLUMNS.map((label) => (
              <SitesColumnHeader
                key={label}
                label={label}
                onResizeStart={handleResizeStart}
                onResizeKeyDown={handleResizeKeyDown}
                onResizeReset={handleResizeReset}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sites.map((site) => (
            <SiteRow key={site.id} site={site} onManage={onManage} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
