/* oxlint-disable react-perf/jsx-no-new-function-as-prop, react-perf/jsx-no-jsx-as-prop, react-perf/jsx-no-new-array-as-prop, react-perf/jsx-no-new-object-as-prop, react/no-array-index-key -- Dialog callbacks, live pixel size, and Base UI render props use import state. */

import { useEffect, useState, type ChangeEvent, type KeyboardEvent, type PointerEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Spinner } from "@/components/ui/spinner"

import { PreviewBody } from "./canned-import-preview"
import { useImportDialog, type SiteOption } from "./canned-import-state"

const IMPORT_DIALOG_DEFAULT = { width: 768, height: 720 }
const IMPORT_DIALOG_MIN = { width: 520, height: 440 }
const IMPORT_DIALOG_PAD = 32
const IMPORT_DIALOG_ASPECT = IMPORT_DIALOG_DEFAULT.width / IMPORT_DIALOG_DEFAULT.height

const clampDialogSize = (width: number) => {
  const maxWidth = Math.max(1, window.innerWidth - IMPORT_DIALOG_PAD)
  const maxHeight = Math.max(1, window.innerHeight - IMPORT_DIALOG_PAD)
  const maxAspectWidth = Math.min(maxWidth, maxHeight * IMPORT_DIALOG_ASPECT)
  const minAspectWidth = Math.min(
    maxAspectWidth,
    Math.max(IMPORT_DIALOG_MIN.width, IMPORT_DIALOG_MIN.height * IMPORT_DIALOG_ASPECT),
  )
  const nextWidth = Math.min(maxAspectWidth, Math.max(minAspectWidth, width))
  const nextHeight = nextWidth / IMPORT_DIALOG_ASPECT

  return {
    width: Math.round(nextWidth),
    height: Math.round(nextHeight),
  }
}

const useImportDialogSize = () => {
  const [size, setSize] = useState(IMPORT_DIALOG_DEFAULT)
  useEffect(() => {
    const handleResize = () => setSize((current) => clampDialogSize(current.width))
    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])
  const handlePointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    const handle = event.currentTarget
    const pointerId = event.pointerId
    if (typeof handle.setPointerCapture === "function") {
      handle.setPointerCapture(pointerId)
    }
    const startX = event.clientX
    const startY = event.clientY
    const startWidth = size.width
    const startHeight = size.height
    const onMove = (move: globalThis.PointerEvent) => {
      const scale =
        ((startWidth + (move.clientX - startX)) / startWidth +
          (startHeight + (move.clientY - startY)) / startHeight) /
        2
      setSize(clampDialogSize(startWidth * scale))
    }
    const release = () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", release)
      window.removeEventListener("pointercancel", release)
      if (
        typeof handle.hasPointerCapture === "function" &&
        handle.hasPointerCapture(pointerId) &&
        typeof handle.releasePointerCapture === "function"
      ) {
        handle.releasePointerCapture(pointerId)
      }
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", release)
    window.addEventListener("pointercancel", release)
  }
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const step = event.shiftKey ? 40 : 16
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault()
      setSize((current) => clampDialogSize(current.width + step))
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault()
      setSize((current) => clampDialogSize(current.width - step))
    }
  }
  return {
    size,
    resetSize: () => setSize(clampDialogSize(IMPORT_DIALOG_DEFAULT.width)),
    handlePointerDown,
    handleKeyDown,
  }
}

const ImportFilePicker = ({
  file,
  compact,
  onFile,
}: {
  file: File | null
  compact: boolean
  onFile: (event: ChangeEvent<HTMLInputElement>) => void
}) => (
  <label
    className={`text-ink flex cursor-pointer flex-col items-center justify-center gap-2 px-4 text-center text-sm font-medium ${
      compact ? "py-4" : "min-h-0 flex-1 py-10"
    }`}
  >
    <span>CSV file</span>
    <input
      type="file"
      accept=".csv,text/csv"
      onChange={onFile}
      aria-label="LiveChat canned responses CSV"
      className="peer sr-only"
    />
    <span className="border-line bg-paper text-navy peer-focus-visible:ring-steel rounded-[8px] border px-4 py-1.5 text-xs font-bold peer-focus-visible:ring-2">
      {file ? "Choose a different file" : "Choose file"}
    </span>
    <span className="text-mute max-w-full truncate text-xs font-normal">
      {file ? file.name : "No file chosen"}
    </span>
  </label>
)

const ImportDialogActions = ({
  previewReady,
  canImport,
  busy,
  hasFile,
  onClose,
  onPreview,
  onImport,
}: {
  previewReady: boolean
  canImport: boolean
  busy: boolean
  hasFile: boolean
  onClose: () => void
  onPreview: () => void
  onImport: () => void
}) => (
  <DialogFooter className="relative flex-row items-center justify-end gap-2 pe-11">
    <Button type="button" variant="outline" onClick={onClose}>
      Cancel
    </Button>
    {previewReady ? (
      <Button variant="default" disabled={!canImport} onClick={onImport}>
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {busy ? "Importing…" : "Import responses"}
      </Button>
    ) : (
      <Button variant="default" disabled={!hasFile || busy} onClick={onPreview}>
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {busy ? "Reading…" : "Preview"}
      </Button>
    )}
  </DialogFooter>
)

const ImportResizeHandle = ({
  onPointerDown,
  onKeyDown,
  onReset,
}: {
  onPointerDown: (event: PointerEvent<HTMLButtonElement>) => void
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void
  onReset: () => void
}) => (
  <button
    type="button"
    aria-label="Resize dialog"
    title="Drag to resize. Aspect ratio stays locked. Arrow keys adjust. Double-click resets."
    onPointerDown={onPointerDown}
    onKeyDown={onKeyDown}
    onDoubleClick={onReset}
    className="text-mute hover:text-ink focus-visible:text-steel absolute right-1.5 bottom-1.5 z-30 grid size-6 cursor-se-resize touch-none place-items-center rounded-none bg-transparent transition-colors duration-150 outline-none"
  >
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="size-4 stroke-current"
      fill="none"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d="M14 4 L4 14" />
      <path d="M14 9 L9 14" />
    </svg>
  </button>
)

export const ImportDialog = ({
  open,
  onClose,
  onImported,
  sites,
}: {
  open: boolean
  onClose: () => void
  onImported: () => Promise<void>
  sites: SiteOption[]
}) => {
  const dialog = useImportDialog({ onClose, onImported })
  const resize = useImportDialogSize()
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) dialog.handleClose()
      }}
    >
      <DialogContent
        className="h-auto max-h-none w-auto max-w-none"
        style={{ width: resize.size.width, height: resize.size.height }}
      >
        <DialogHeader>
          <DialogTitle>Import LiveChat canned responses</DialogTitle>
          <DialogDescription>
            Choose a LiveChat canned responses CSV. Preview the rows, map each LiveChat website to
            one we host, then import them into this library.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 scrollbar-gutter-stable flex-col gap-3 overflow-y-auto px-5 py-3 pr-4">
          <ImportFilePicker
            file={dialog.file}
            compact={!!dialog.preview}
            onFile={dialog.handleFile}
          />
          {dialog.preview ? (
            <PreviewBody
              preview={dialog.preview}
              sites={sites}
              selected={dialog.selected}
              groupTargets={dialog.groupTargets}
              onSelected={dialog.setSelected}
              onGroupTarget={(group, target) =>
                dialog.setGroupTargets((current) => ({ ...current, [group]: target }))
              }
            />
          ) : null}
          {dialog.error ? <p className="text-ember text-sm">{dialog.error}</p> : null}
        </div>
        <ImportDialogActions
          previewReady={!!dialog.preview}
          canImport={dialog.canImport}
          busy={dialog.busy}
          hasFile={!!dialog.file}
          onClose={dialog.handleClose}
          onPreview={() => void dialog.handlePreview()}
          onImport={() => void dialog.handleImport()}
        />
        <ImportResizeHandle
          onPointerDown={resize.handlePointerDown}
          onKeyDown={resize.handleKeyDown}
          onReset={resize.resetSize}
        />
      </DialogContent>
    </Dialog>
  )
}
