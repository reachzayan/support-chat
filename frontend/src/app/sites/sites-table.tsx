"use client"

import { Settings2 } from "lucide-react"
import { useCallback, useMemo } from "react"

import type { SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { StateIcon } from "@/components/ui/state-icon"

import { CopyButton } from "./copy-button"
import { useSitesColumnWidths } from "./sites-column-widths"
import { COLUMNS, LABEL, type ColumnLabel } from "./sites-shared"

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
      className={`${LABEL} border-line relative border-r px-3 py-2.5 last:border-r-0`}
    >
      <span className="pr-3">{label}</span>
      <Button
        type="button"
        variant="ghost"
        aria-label={`Resize ${label} column`}
        title="Drag to resize. Arrow keys adjust. Double-click resets."
        onPointerDown={handlePointerDown}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleReset}
        className="focus-visible:ring-steel absolute top-0 right-0 z-10 h-full w-3 cursor-col-resize touch-none border-0 bg-transparent p-0 focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="bg-line hover:bg-steel focus-visible:bg-steel absolute top-1.5 right-0 bottom-1.5 w-px" />
      </Button>
    </th>
  )
}

const InstalledCell = ({
  site,
  isAdmin,
  checking,
  onCheckInstall,
}: {
  site: SiteRecord
  isAdmin: boolean
  checking: boolean
  onCheckInstall: (siteId: string) => void
}) => {
  const handleRefresh = useCallback(() => onCheckInstall(site.id), [onCheckInstall, site.id])

  if (!site.website_url) {
    return <span className="text-mute text-xs">No website URL</span>
  }

  const pillClass =
    site.widget_installed === true
      ? "bg-steel/10 text-steel"
      : site.widget_installed === false
        ? "bg-ember/10 text-ember"
        : "bg-ice text-mute"
  const pillLabel =
    site.widget_installed === true
      ? "Installed"
      : site.widget_installed === false
        ? "Not installed"
        : "Not checked"

  return (
    <div className="flex items-center gap-1.5">
      <span className={`rounded-[6px] px-1.5 py-0.5 text-[10px] font-bold ${pillClass}`}>
        {pillLabel}
      </span>
      {isAdmin ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={handleRefresh}
          disabled={checking}
          aria-label={`Recheck install status for ${site.name}`}
          title="Recheck install status"
          className="text-mute hover:text-steel focus-visible:ring-steel focus-visible:ring-2 focus-visible:outline-none"
        >
          {checking ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <StateIcon name="arrow-clockwise" className="size-3.5" />
          )}
        </Button>
      ) : null}
    </div>
  )
}

const SiteRow = ({
  site,
  isAdmin,
  onManage,
  checking,
  onCheckInstall,
}: {
  site: SiteRecord
  isAdmin: boolean
  onManage: (siteId: string) => void
  checking: boolean
  onCheckInstall: (siteId: string) => void
}) => {
  const publicPreview = `${site.public_key.slice(0, 6)}…${site.public_key.slice(-4)}`
  const originLabel = site.origins.length === 1 ? "1 origin" : `${site.origins.length} origins`
  const handleManage = useCallback(() => onManage(site.id), [onManage, site.id])
  const siteOn = site.enabled !== false

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
      <td className="px-3 py-2.5" aria-label="Widget install status">
        <InstalledCell
          site={site}
          isAdmin={isAdmin}
          checking={checking}
          onCheckInstall={onCheckInstall}
        />
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center justify-center">
          <CopyButton value={site.snippet} className="rounded-r-none" />
          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={handleManage}
            className="rounded-l-none border-l-0"
          >
            <Settings2 data-icon="inline-start" aria-hidden="true" />
            Manage
          </Button>
        </div>
      </td>
    </tr>
  )
}

export const SitesTable = ({
  sites,
  isAdmin,
  onManage,
  checkingIds,
  onCheckInstall,
}: {
  sites: SiteRecord[]
  isAdmin: boolean
  onManage: (siteId: string) => void
  checkingIds: string[]
  onCheckInstall: (siteId: string) => void
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
            <SiteRow
              key={site.id}
              site={site}
              isAdmin={isAdmin}
              onManage={onManage}
              checking={checkingIds.includes(site.id)}
              onCheckInstall={onCheckInstall}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
