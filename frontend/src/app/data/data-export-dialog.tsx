"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import { staffRead, staffWrite, type SiteRecord } from "@/components/admin/staff-api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldError } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"

import {
  ALL_SITES,
  ExportColumnPicker,
  ExportDateFields,
  ExportSiteField,
} from "./data-export-fields"
import { EXPORT_COLUMNS, type ColumnLabel } from "./data-shared"

type DataExportDialogProps = {
  open: boolean
  onClose: () => void
}

export const DataExportDialog = ({ open, onClose }: DataExportDialogProps) => {
  const state = useExportForm(open, onClose)
  return (
    <Dialog open={open} onOpenChange={state.handleOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Export submissions</DialogTitle>
          <DialogDescription>
            Choose columns, a date range, and a site. The file does not include full chat
            transcripts.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
          <ExportColumnPicker
            columns={state.columns}
            onToggle={state.handleToggleColumn}
            onSelectAll={state.handleSelectAll}
          />
          <ExportDateFields
            dateFrom={state.dateFrom}
            dateTo={state.dateTo}
            onDateFrom={state.setDateFrom}
            onDateTo={state.setDateTo}
          />
          <ExportSiteField
            siteId={state.siteId}
            sites={state.sites}
            siteItems={state.siteItems}
            onSiteId={state.setSiteId}
          />
          <FieldError>{state.error || undefined}</FieldError>
        </div>
        <DataExportActions
          submitting={state.submitting}
          canDownload={state.columns.length > 0}
          onClose={state.handleClose}
          onDownload={state.handleDownloadClick}
        />
      </DialogContent>
    </Dialog>
  )
}

// eslint-disable-next-line max-lines-per-function -- export form state, load, and download
const useExportForm = (open: boolean, onClose: () => void) => {
  const [columns, setColumns] = useState<ColumnLabel[]>([...EXPORT_COLUMNS])
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [siteId, setSiteId] = useState(ALL_SITES)
  const [sites, setSites] = useState<SiteRecord[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!open) {
      return
    }
    let ignore = false
    const load = async () => {
      try {
        const response = await staffRead("/api/sites")
        if (!response.ok || ignore) {
          return
        }
        const body = (await response.json()) as { items: SiteRecord[] }
        if (!ignore) {
          setSites(body.items)
        }
      } catch {
        if (!ignore) {
          setSites([])
        }
      }
    }
    void load()
    return () => {
      ignore = true
    }
  }, [open])

  const siteItems = useMemo(
    () =>
      Object.fromEntries([[ALL_SITES, "All sites"], ...sites.map((site) => [site.id, site.name])]),
    [sites],
  )

  const handleClose = useCallback(() => {
    if (!submitting) {
      onClose()
    }
  }, [onClose, submitting])

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) {
        handleClose()
      }
    },
    [handleClose],
  )

  const handleToggleColumn = useCallback((column: ColumnLabel, checked: boolean) => {
    setColumns((current) => {
      if (checked) {
        return EXPORT_COLUMNS.filter((item) => item === column || current.includes(item))
      }
      return current.filter((item) => item !== column)
    })
  }, [])

  const handleSelectAll = useCallback(() => {
    setColumns((current) => (current.length === EXPORT_COLUMNS.length ? [] : [...EXPORT_COLUMNS]))
  }, [])

  const handleDownload = useCallback(async () => {
    if (submitting || columns.length === 0) {
      return
    }
    setSubmitting(true)
    setError("")
    try {
      const response = await staffWrite("/api/conversations/submissions/export", "POST", {
        columns,
        site_id: siteId === ALL_SITES ? null : siteId,
        date_from: dateFrom || null,
        date_to: dateTo || null,
      })
      if (!response.ok) {
        setError("Export could not be created. Try again.")
        return
      }
      const blob = await response.blob()
      const href = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = href
      link.download = "supportchat-submissions.csv"
      link.click()
      URL.revokeObjectURL(href)
      onClose()
    } catch {
      setError("Export could not be created. Try again.")
    } finally {
      setSubmitting(false)
    }
  }, [columns, dateFrom, dateTo, onClose, siteId, submitting])

  const handleDownloadClick = useCallback(() => {
    void handleDownload()
  }, [handleDownload])

  return {
    columns,
    dateFrom,
    dateTo,
    siteId,
    sites,
    siteItems,
    submitting,
    error,
    setDateFrom,
    setDateTo,
    setSiteId,
    handleClose,
    handleOpenChange,
    handleToggleColumn,
    handleSelectAll,
    handleDownloadClick,
  }
}

const DataExportActions = ({
  submitting,
  canDownload,
  onClose,
  onDownload,
}: {
  submitting: boolean
  canDownload: boolean
  onClose: () => void
  onDownload: () => void
}) => (
  <DialogFooter className="flex-row items-center justify-end gap-2">
    <Button type="button" variant="outline" size="lg" onClick={onClose}>
      Cancel
    </Button>
    <Button
      type="button"
      variant="default"
      size="lg"
      disabled={submitting || !canDownload}
      onClick={onDownload}
    >
      {submitting ? <Spinner data-icon="inline-start" /> : null}
      {submitting ? "Exporting…" : "Download"}
    </Button>
  </DialogFooter>
)
